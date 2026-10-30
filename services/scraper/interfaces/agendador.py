"""Ponto de entrada do scraper: monta as peças e roda rodadas de coleta.

Uso, dentro de services/scraper com o .venv ativo:
    python -m interfaces.agendador                      # roda para sempre, a cada 30 min
    python -m interfaces.agendador --uma-vez            # roda uma rodada e sai
    python -m interfaces.agendador --intervalo-minutos 5

Sem REDIS_URL no ambiente (ou --redis-url), as promoções só aparecem no console.
Com ele, vão para o stream `promocoes` do Redis, de onde o notifier as lê.
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
    logger.info("Publicando promoções no Redis em %s", redis_url)
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


def main(argumentos: Optional[list[str]] = None) -> None:
    carregar_dotenv(ENV_PADRAO)  # antes do parser, porque o padrão de --redis-url lê o ambiente

    parser = argparse.ArgumentParser(description="Agendador do scraper de promoções")
    parser.add_argument(
        "--produtos", type=Path, default=ARQUIVO_PADRAO, help="arquivo JSON com os produtos"
    )
    parser.add_argument(
        "--intervalo-minutos", type=float, default=30, help="tempo entre rodadas"
    )
    parser.add_argument("--uma-vez", action="store_true", help="roda uma rodada e sai")
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL"),
        help="endereço do Redis (padrão: variável REDIS_URL; vazio usa o console)",
    )
    opcoes = parser.parse_args(argumentos)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    fonte = FonteDeProdutosJson(opcoes.produtos)
    repositorio = OfertaRepositorioEmMemoria()  # histórico vive só enquanto o processo roda
    publicador = montar_publicador(opcoes.redis_url)

    while True:
        publicadas = executar_rodada(fonte, repositorio, publicador)
        logger.info("Rodada concluída: %d promoção(ões) publicada(s)", publicadas)
        if opcoes.uma_vez:
            break
        time.sleep(opcoes.intervalo_minutos * 60)


if __name__ == "__main__":
    main()
