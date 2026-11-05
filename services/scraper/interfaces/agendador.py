"""Ponto de entrada do scraper: monta as peças e roda rodadas de coleta.

Uso, dentro de services/scraper com o .venv ativo:
    python -m interfaces.agendador                      # roda para sempre, no intervalo configurado
    python -m interfaces.agendador --uma-vez            # roda uma rodada e sai
    python -m interfaces.agendador --intervalo-minutos 5

PERSISTENCIA escolhe postgres ou memoria; FONTE_PRODUTOS escolhe json ou postgres.
EVENTOS_TRANSPORTE escolhe console, redis ou postgres (fila ainda sem consumidor Go).
Quando EVENTOS_TRANSPORTE=redis, REDIS_URL configura a publicação no Redis.
SCRAPER_INTERVALO_MINUTOS define o intervalo entre rodadas (padrão 30);
--intervalo-minutos tem prioridade sobre ela.
O .env da raiz do projeto é lido na partida, então basta preenchê-lo uma vez.
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

from application.portas import (
    TIPO_LISTAGEM,
    TIPO_PRODUTO,
    ColetorDePrecos,
    FonteDeProdutosMonitorados,
    PrecoColetado,
    ProdutoMonitorado,
    PublicadorDeEventos,
)
from application.processar_coleta import ProcessarColeta
from domain.repositorios import OfertaRepositorio
from infrastructure.mensageria.console import PublicadorNoConsole
from infrastructure.mensageria.redis_streams import PublicadorRedis
from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria
from infrastructure.persistencia.produtos_json import FonteDeProdutosJson
from infrastructure.scrapers.americanas import LOJA as AMERICANAS
from infrastructure.scrapers.americanas import ColetorAmericanas
from infrastructure.scrapers.americanas_listagem import ColetorListagemAmericanas
from infrastructure.scrapers.kabum import LOJA as KABUM
from infrastructure.scrapers.kabum import ColetorKabum
from infrastructure.scrapers.kabum_listagem import ColetorListagemKabum

logger = logging.getLogger(__name__)

ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent / "produtos.json"
ENV_PADRAO = Path(__file__).resolve().parent.parent.parent.parent / ".env"

# Para adicionar uma loja: escreva o adaptador em infrastructure/scrapers e registre aqui,
# pela chave (loja, tipo). Uma loja pode ter coletor de produto avulso, de listagem ou os dois.
FabricaDeColetor = Callable[[list[ProdutoMonitorado]], ColetorDePrecos]
FABRICAS_DE_COLETOR: dict[tuple[str, str], FabricaDeColetor] = {
    (KABUM, TIPO_PRODUTO): lambda itens: ColetorKabum(urls=[item.url for item in itens]),
    (KABUM, TIPO_LISTAGEM): lambda itens: ColetorListagemKabum(listagens=itens),
    (AMERICANAS, TIPO_PRODUTO): lambda itens: ColetorAmericanas(urls=[item.url for item in itens]),
    (AMERICANAS, TIPO_LISTAGEM): lambda itens: ColetorListagemAmericanas(listagens=itens),
}


class ColetorComposto(ColetorDePrecos):
    """Junta os coletores de todas as lojas num único ColetorDePrecos."""

    def __init__(self, coletores: list[ColetorDePrecos]):
        self.coletores = coletores

    def coletar(self) -> list[PrecoColetado]:
        itens: list[PrecoColetado] = []
        for coletor in self.coletores:
            itens.extend(coletor.coletar())
        return itens


def montar_coletor(
    produtos: list[ProdutoMonitorado],
    fabricas: dict[tuple[str, str], FabricaDeColetor] = FABRICAS_DE_COLETOR,
) -> ColetorComposto:
    """Agrupa os itens por (loja, tipo) e cria um coletor para cada grupo conhecido."""
    grupos: dict[tuple[str, str], list[ProdutoMonitorado]] = {}
    for produto in produtos:
        grupos.setdefault((produto.loja, produto.tipo), []).append(produto)

    coletores: list[ColetorDePrecos] = []
    for (loja, tipo), itens in grupos.items():
        fabrica = fabricas.get((loja, tipo))
        if fabrica is None:
            logger.warning(
                "Loja '%s' não tem scraper de %s; %d item(ns) ignorado(s)", loja, tipo, len(itens)
            )
            continue
        coletores.append(fabrica(itens))

    return ColetorComposto(coletores)


def executar_rodada(
    fonte: FonteDeProdutosMonitorados,
    repositorio: OfertaRepositorio,
    publicador: PublicadorDeEventos,
    fabricas: dict[tuple[str, str], FabricaDeColetor] = FABRICAS_DE_COLETOR,
) -> int:
    """Uma rodada completa: lê a lista, coleta, processa e devolve quantas promoções saíram."""
    produtos = fonte.listar()
    coletor = montar_coletor(produtos, fabricas)
    caso_de_uso = ProcessarColeta(coletor, repositorio, publicador)
    return caso_de_uso.executar()


def montar_publicador(redis_url: Optional[str]) -> PublicadorDeEventos:
    """Redis quando há URL configurada; console caso contrário."""
    if not redis_url:
        logger.info("REDIS_URL não definida: promoções serão impressas no console")
        return PublicadorNoConsole()

    import redis  # importado aqui para que o console funcione mesmo sem o pacote

    cliente = redis.from_url(redis_url, decode_responses=True)
    cliente.ping()  # falha já na partida se o Redis não estiver acessível
    logger.info("Publicando promoções no Redis")
    return PublicadorRedis(cliente)


def carregar_dotenv(caminho: Path) -> None:
    """Lê linhas CHAVE=VALOR e define só as variáveis que ainda não existem no ambiente.

    Arquivo inexistente não é erro: em produção a configuração vem do ambiente.
    """
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip("\"'")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


INTERVALO_PADRAO_MINUTOS = 30


def minutos_positivos(texto: str) -> float:
    """Converte "15", "7.5" ou "7,5" em minutos; recusa zero, negativo e texto."""
    try:
        minutos = float(str(texto).strip().replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} não é um número de minutos")
    if minutos <= 0:
        raise argparse.ArgumentTypeError("o intervalo precisa ser maior que zero")
    return minutos


def montar_parser() -> argparse.ArgumentParser:
    """Opções da linha de comando; os padrões vêm do ambiente, já com o .env carregado."""
    parser = argparse.ArgumentParser(description="Agendador do scraper de promoções")
    parser.add_argument(
        "--produtos", type=Path, default=ARQUIVO_PADRAO, help="arquivo JSON com os produtos"
    )
    parser.add_argument(
        "--intervalo-minutos",
        type=minutos_positivos,
        default=os.environ.get("SCRAPER_INTERVALO_MINUTOS") or str(INTERVALO_PADRAO_MINUTOS),
        help="tempo entre rodadas (padrão: variável SCRAPER_INTERVALO_MINUTOS, ou 30)",
    )
    parser.add_argument("--uma-vez", action="store_true", help="roda uma rodada e sai")
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL"),
        help="endereço do Redis (padrão: REDIS_URL; usado com --eventos redis)",
    )
    parser.add_argument(
        "--persistencia", choices=["memoria", "postgres"],
        default=os.environ.get("PERSISTENCIA", "postgres"),
    )
    parser.add_argument(
        "--fonte-produtos", choices=["json", "postgres"],
        default=os.environ.get("FONTE_PRODUTOS", "json"),
    )
    parser.add_argument(
        "--eventos", choices=["console", "redis", "postgres"],
        default=os.environ.get("EVENTOS_TRANSPORTE", "console"),
    )
    return parser


def main(argumentos: Optional[list[str]] = None) -> None:
    carregar_dotenv(ENV_PADRAO)
    parser = montar_parser()
    opcoes = parser.parse_args(argumentos)
    for nome, valor, permitidos in (
        ("PERSISTENCIA", opcoes.persistencia, ("memoria", "postgres")),
        ("FONTE_PRODUTOS", opcoes.fonte_produtos, ("json", "postgres")),
        ("EVENTOS_TRANSPORTE", opcoes.eventos, ("console", "redis", "postgres")),
    ):
        if valor not in permitidos:
            parser.error(f"{nome} inválida: escolha {', '.join(permitidos)}")
    if opcoes.eventos == "postgres" and opcoes.persistencia != "postgres":
        parser.error("--eventos postgres exige --persistencia postgres")
    if opcoes.eventos == "redis" and not opcoes.redis_url:
        parser.error("--eventos redis exige REDIS_URL ou --redis-url")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    conexao = None
    try:
        if opcoes.persistencia == "postgres" or opcoes.fonte_produtos == "postgres":
            from infrastructure.persistencia.postgres import (
                FonteDeProdutosPostgres, OfertaRepositorioPostgres, conectar,
            )
            conexao = conectar(os.environ.get("DATABASE_URL", ""))
        fonte = (FonteDeProdutosPostgres(conexao) if opcoes.fonte_produtos == "postgres"
                 else FonteDeProdutosJson(opcoes.produtos))
        repositorio = (OfertaRepositorioPostgres(conexao) if opcoes.persistencia == "postgres"
                       else OfertaRepositorioEmMemoria())
        if opcoes.eventos == "postgres":
            from infrastructure.mensageria.postgres import PublicadorPostgres
            publicador = PublicadorPostgres(conexao)
        else:
            publicador = montar_publicador(opcoes.redis_url if opcoes.eventos == "redis" else None)

        if not opcoes.uma_vez:
            logger.info("Rodadas a cada %g minuto(s)", opcoes.intervalo_minutos)

        while True:
            publicadas = executar_rodada(fonte, repositorio, publicador)
            logger.info("Rodada concluída: %d promoção(ões) publicada(s)", publicadas)
            if opcoes.uma_vez:
                break
            time.sleep(opcoes.intervalo_minutos * 60)
    except Exception:
        # Drivers podem incluir credenciais na mensagem de erro; não imprimir traceback/DSN.
        logger.error("Coleta interrompida. Confira a configuração escolhida, conexão, SSL e "
                     "tabelas de sql/schema.sql. Não houve troca automática para memória.")
        raise SystemExit(1) from None
    finally:
        if conexao is not None:
            conexao.close()


if __name__ == "__main__":
    main()
