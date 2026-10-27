from decimal import Decimal
from pathlib import Path

import pytest
import requests

from infrastructure.scrapers.kabum import (
    LOJA,
    ColetorKabum,
    PaginaInvalida,
    extrair_produto,
)

FIXTURES = Path(__file__).parent / "fixtures"
URL_EM_ESTOQUE = "https://www.kabum.com.br/produto/415807/water-cooler-nzxt"
URL_SEM_ESTOQUE = "https://www.kabum.com.br/produto/412289/computador-lenovo"


def ler_fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


# --- extrair_produto: função pura, sem rede -------------------------------


def test_extrai_preco_avista_como_decimal_exato():
    produto = extrair_produto(ler_fixture("kabum_produto_em_estoque.html"))

    assert produto.produto_id == "415807"
    assert produto.nome.startswith("Water Cooler NZXT Kraken Elite 240")
    assert produto.disponivel is True
    assert produto.preco_avista == Decimal("1569.99")
    assert isinstance(produto.preco_avista, Decimal)


def test_extrai_produto_sem_estoque():
    produto = extrair_produto(ler_fixture("kabum_produto_sem_estoque.html"))

    assert produto.produto_id == "412289"
    assert produto.disponivel is False
    assert produto.preco_avista == Decimal("5720.06")


def test_pagina_sem_next_data_e_invalida():
    with pytest.raises(PaginaInvalida):
        extrair_produto("<html><body>pagina qualquer</body></html>")


def test_pagina_sem_produto_e_invalida():
    html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'
    with pytest.raises(PaginaInvalida):
        extrair_produto(html)


# --- ColetorKabum: junta download e extração ------------------------------


class DownloadFalso:
    """Substitui o acesso à internet: devolve o HTML de exemplo de cada URL."""

    def __init__(self, paginas: dict[str, str]):
        self.paginas = paginas
        self.urls_pedidas: list[str] = []

    def __call__(self, url: str) -> str:
        self.urls_pedidas.append(url)
        resultado = self.paginas[url]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def montar(paginas: dict[str, str]):
    baixar = DownloadFalso(paginas)
    esperas: list[float] = []
    coletor = ColetorKabum(
        urls=list(paginas),
        baixar=baixar,
        intervalo_segundos=2.0,
        esperar=esperas.append,
    )
    return coletor, baixar, esperas


def test_coleta_produto_em_estoque_com_loja_kabum():
    coletor, _, _ = montar({URL_EM_ESTOQUE: ler_fixture("kabum_produto_em_estoque.html")})

    itens = coletor.coletar()

    assert len(itens) == 1
    assert itens[0].produto_id == "415807"
    assert itens[0].loja == LOJA == "kabum"
    assert itens[0].preco.valor == Decimal("1569.99")


def test_ignora_produto_sem_estoque():
    coletor, _, _ = montar(
        {
            URL_EM_ESTOQUE: ler_fixture("kabum_produto_em_estoque.html"),
            URL_SEM_ESTOQUE: ler_fixture("kabum_produto_sem_estoque.html"),
        }
    )

    itens = coletor.coletar()

    assert [item.produto_id for item in itens] == ["415807"]


def test_espera_o_intervalo_entre_requisicoes_mas_nao_antes_da_primeira():
    coletor, baixar, esperas = montar(
        {
            URL_EM_ESTOQUE: ler_fixture("kabum_produto_em_estoque.html"),
            URL_SEM_ESTOQUE: ler_fixture("kabum_produto_sem_estoque.html"),
        }
    )

    coletor.coletar()

    assert baixar.urls_pedidas == [URL_EM_ESTOQUE, URL_SEM_ESTOQUE]
    assert esperas == [2.0]


def test_falha_em_uma_pagina_nao_derruba_a_rodada():
    coletor, _, _ = montar(
        {
            "https://www.kabum.com.br/produto/1/fora-do-ar": requests.ConnectionError("timeout"),
            "https://www.kabum.com.br/produto/2/mudou-o-site": "<html>sem next data</html>",
            URL_EM_ESTOQUE: ler_fixture("kabum_produto_em_estoque.html"),
        }
    )

    itens = coletor.coletar()

    assert [item.produto_id for item in itens] == ["415807"]
