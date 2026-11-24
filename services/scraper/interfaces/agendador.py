"""Ponto de entrada do scraper: lê a configuração e roda rodadas de coleta.

Quais peças usar e como ligá-las fica em interfaces/composicao.py; aqui ficam a
linha de comando, a leitura do .env e o laço das rodadas.

Uso, dentro de services/scraper com o .venv ativo:
    python -m interfaces.agendador                      # roda para sempre, no intervalo configurado
    python -m interfaces.agendador --uma-vez            # roda uma rodada e sai
    python -m interfaces.agendador --intervalo-minutos 5
    python -m interfaces.agendador --uma-vez --limite-urls 3   # rodada curta, para testar

PERSISTENCIA escolhe postgres ou memoria; FONTE_PRODUTOS escolhe json ou postgres.
EVENTOS_TRANSPORTE escolhe console, redis ou postgres (fila ainda sem consumidor Go).
Quando EVENTOS_TRANSPORTE=redis, REDIS_URL configura a publicação no Redis.
SCRAPER_INTERVALO_MINUTOS define o intervalo entre rodadas (padrão 15);
--intervalo-minutos tem prioridade sobre ela.
O .env da raiz do projeto é lido na partida, então basta preenchê-lo uma vez.
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

from interfaces.composicao import (
    ARQUIVO_PADRAO,
    FONTES_DE_PRODUTOS,
    PERSISTENCIAS,
    TRANSPORTES_DE_EVENTOS,
    Configuracao,
    ConfiguracaoInvalida,
    Montagem,
)

logger = logging.getLogger(__name__)

ENV_PADRAO = Path(__file__).resolve().parent.parent.parent.parent / ".env"


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


INTERVALO_PADRAO_MINUTOS = 15


def minutos_positivos(texto: str) -> float:
    """Converte "15", "7.5" ou "7,5" em minutos; recusa zero, negativo e texto."""
    try:
        minutos = float(str(texto).strip().replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} não é um número de minutos")
    if minutos <= 0:
        raise argparse.ArgumentTypeError("o intervalo precisa ser maior que zero")
    return minutos


def inteiro_positivo(texto: str) -> int:
    """Converte "3" em 3; recusa zero, negativo, decimal e texto."""
    try:
        numero = int(str(texto).strip())
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} não é um número inteiro")
    if numero <= 0:
        raise argparse.ArgumentTypeError("o limite precisa ser maior que zero")
    return numero


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
        help="tempo entre rodadas (padrão: variável SCRAPER_INTERVALO_MINUTOS, ou 15)",
    )
    parser.add_argument("--uma-vez", action="store_true", help="roda uma rodada e sai")
    parser.add_argument(
        "--limite-urls", type=inteiro_positivo, default=None, metavar="N",
        help="rodada curta para teste: coleta só N endereços (alterna entre as lojas; "
             "listagens seguem só a 1ª página)",
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL"),
        help="endereço do Redis (padrão: REDIS_URL; usado com --eventos redis)",
    )
    parser.add_argument(
        "--persistencia", choices=PERSISTENCIAS,
        default=os.environ.get("PERSISTENCIA", "postgres"),
    )
    parser.add_argument(
        "--fonte-produtos", choices=FONTES_DE_PRODUTOS,
        default=os.environ.get("FONTE_PRODUTOS", "json"),
    )
    parser.add_argument(
        "--eventos", choices=TRANSPORTES_DE_EVENTOS,
        default=os.environ.get("EVENTOS_TRANSPORTE", "console"),
    )
    return parser


ESPERA_APOS_FALHA_SEGUNDOS = 60


def executar_em_laco(
    rodada: Callable[[], int],
    intervalo_segundos: float,
    uma_vez: bool = False,
    esperar: Callable[[float], None] = time.sleep,
) -> None:
    """Roda a rodada para sempre; uma rodada com erro não derruba o scraper.

    Depois de uma falha, tenta de novo em 1 minuto (ou no intervalo, se for
    menor), para não ficar meia hora parado por uma queda rápida do banco.
    Com uma_vez, o erro sobe para quem chamou encerrar com código de falha.
    """
    while True:
        try:
            publicadas = rodada()
        except Exception as erro:
            if uma_vez:
                raise
            espera = min(intervalo_segundos, ESPERA_APOS_FALHA_SEGUNDOS)
            # Só o tipo do erro: a mensagem de drivers pode carregar DSN e senha.
            logger.error(
                "Rodada falhou (%s); nova tentativa em %g segundo(s)",
                type(erro).__name__, espera,
            )
        else:
            logger.info("Rodada concluída: %d promoção(ões) publicada(s)", publicadas)
            if uma_vez:
                return
            espera = intervalo_segundos
        esperar(espera)


def main(argumentos: Optional[list[str]] = None) -> None:
    carregar_dotenv(ENV_PADRAO)
    parser = montar_parser()
    opcoes = parser.parse_args(argumentos)
    config = Configuracao(
        persistencia=opcoes.persistencia,
        fonte_produtos=opcoes.fonte_produtos,
        eventos=opcoes.eventos,
        produtos=opcoes.produtos,
        redis_url=opcoes.redis_url,
        database_url=os.environ.get("DATABASE_URL", ""),
        limite_urls=opcoes.limite_urls,
    )
    try:
        config.validar()
    except ConfiguracaoInvalida as erro:
        parser.error(str(erro))

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    montagem = Montagem(config)
    try:
        montagem.iniciar()
        if config.limite_urls:
            logger.info("Modo de teste: cada rodada coleta no máximo %d endereço(s)", config.limite_urls)
        if not opcoes.uma_vez:
            logger.info("Rodadas a cada %g minuto(s)", opcoes.intervalo_minutos)
        executar_em_laco(
            montagem.rodada, opcoes.intervalo_minutos * 60, uma_vez=opcoes.uma_vez, esperar=time.sleep
        )
    except Exception:
        # Drivers podem incluir credenciais na mensagem de erro; não imprimir traceback/DSN.
        logger.error("Coleta interrompida. Confira a configuração escolhida, conexão, SSL e "
                     "tabelas de sql/schema.sql. Não houve troca automática para memória.")
        raise SystemExit(1) from None
    finally:
        montagem.fechar()


if __name__ == "__main__":
    main()
