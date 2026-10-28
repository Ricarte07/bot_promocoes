"""Ponto de entrada do scraper: monta as peças e roda rodadas de coleta.

Uso, dentro de services/scraper com o .venv ativo:
    python -m interfaces.agendador                      # roda para sempre, a cada 30 min
    python -m interfaces.agendador --uma-vez            # roda uma rodada e sai
    python -m interfaces.agendador --intervalo-minutos 5
"""

import argparse
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from application.portas import (
    ColetorDePrecos,
    FonteDeProdutosMonitorados,
    PrecoColetado,
    ProdutoMonitorado,
    PublicadorDeEventos,
)
from application.processar_coleta import ProcessarColeta
from domain.repositorios import OfertaRepositorio
from infrastructure.mensageria.console import PublicadorNoConsole
from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria
from infrastructure.persistencia.produtos_json import FonteDeProdutosJson
from infrastructure.scrapers.americanas import LOJA as AMERICANAS
from infrastructure.scrapers.americanas import ColetorAmericanas
from infrastructure.scrapers.kabum import LOJA as KABUM
from infrastructure.scrapers.kabum import ColetorKabum

logger = logging.getLogger(__name__)

ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent / "produtos.json"

# Para adicionar uma loja: escreva o adaptador em infrastructure/scrapers e registre aqui.
FabricaDeColetor = Callable[[list[str]], ColetorDePrecos]
FABRICAS_DE_COLETOR: dict[str, FabricaDeColetor] = {
    KABUM: lambda urls: ColetorKabum(urls=urls),
    AMERICANAS: lambda urls: ColetorAmericanas(urls=urls),
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
    fabricas: dict[str, FabricaDeColetor] = FABRICAS_DE_COLETOR,
) -> ColetorComposto:
    """Agrupa as URLs por loja e cria um coletor para cada loja conhecida."""
    urls_por_loja: dict[str, list[str]] = {}
    for produto in produtos:
        urls_por_loja.setdefault(produto.loja, []).append(produto.url)

    coletores: list[ColetorDePrecos] = []
    for loja, urls in urls_por_loja.items():
        fabrica = fabricas.get(loja)
        if fabrica is None:
            logger.warning("Loja '%s' não tem scraper; %d produto(s) ignorado(s)", loja, len(urls))
            continue
        coletores.append(fabrica(urls))

    return ColetorComposto(coletores)


def executar_rodada(
    fonte: FonteDeProdutosMonitorados,
    repositorio: OfertaRepositorio,
    publicador: PublicadorDeEventos,
    fabricas: dict[str, FabricaDeColetor] = FABRICAS_DE_COLETOR,
) -> int:
    """Uma rodada completa: lê a lista, coleta, processa e devolve quantas promoções saíram."""
    produtos = fonte.listar()
    coletor = montar_coletor(produtos, fabricas)
    caso_de_uso = ProcessarColeta(coletor, repositorio, publicador)
    return caso_de_uso.executar()


def main(argumentos: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Agendador do scraper de promoções")
    parser.add_argument(
        "--produtos", type=Path, default=ARQUIVO_PADRAO, help="arquivo JSON com os produtos"
    )
    parser.add_argument(
        "--intervalo-minutos", type=float, default=30, help="tempo entre rodadas"
    )
    parser.add_argument("--uma-vez", action="store_true", help="roda uma rodada e sai")
    opcoes = parser.parse_args(argumentos)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    fonte = FonteDeProdutosJson(opcoes.produtos)
    repositorio = OfertaRepositorioEmMemoria()  # histórico vive só enquanto o processo roda
    publicador = PublicadorNoConsole()

    while True:
        publicadas = executar_rodada(fonte, repositorio, publicador)
        logger.info("Rodada concluída: %d promoção(ões) publicada(s)", publicadas)
        if opcoes.uma_vez:
            break
        time.sleep(opcoes.intervalo_minutos * 60)


if __name__ == "__main__":
    main()
