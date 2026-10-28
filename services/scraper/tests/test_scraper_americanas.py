from decimal import Decimal
from pathlib import Path

import pytest
import requests

from infrastructure.scrapers.americanas import (
    LOJA,
    ColetorAmericanas,
    PaginaInvalida,
    extrair_produto,
)

FIXTURES = Path(__file__).parent / "fixtures"
URL_EM_ESTOQUE = (
    "https://www.americanas.com.br/impressora-epson-ecotank-l1250-tanque-de-tinta-wi-fi-usb-8297500-8776497/p"
)
URL_SEM_ESTOQUE = (
    "https://www.americanas.com.br/cartucho-preto-original-hp-667-ink-advantage-3ym79al-2067629161-2542515/p"
)


def ler_fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def pagina_com_product(product_json: str) -> str:
    return f'<html><head><script type="application/ld+json">{product_json}</script></head></html>'


# --- extrair_produto: função pura, sem rede -------------------------------


def test_extrai_menor_preco_em_estoque_como_decimal_exato():
    produto = extrair_produto(ler_fixture("americanas_produto_em_estoque.html"))

    assert produto.produto_id == "8776497"
    assert produto.nome == "Impressora Epson EcoTank L1250 Wi-Fi Bivolt"
    assert produto.disponivel is True
    # A página tem três ofertas: americanas 949.90, magazineluiza 901.55 e uma esgotada a 0.
    assert produto.preco_avista == Decimal("901.55")
    assert isinstance(produto.preco_avista, Decimal)
    assert produto.vendedor == "magazineluiza"


def test_extrai_produto_sem_estoque():
    produto = extrair_produto(ler_fixture("americanas_produto_sem_estoque.html"))

    assert produto.produto_id == "2542515"
    assert produto.nome == "Cartucho Preto Original HP 667 Ink Advantage 3YM79AL"
    assert produto.disponivel is False
    assert produto.vendedor == ""


def test_ignora_oferta_em_estoque_com_preco_zero():
    html = pagina_com_product(
        '{"@type":"Product","sku":"1","name":"X","offers":['
        '{"@type":"Offer","price":"0","availability":"https://schema.org/InStock"},'
        '{"@type":"Offer","price":"10.50","availability":"https://schema.org/InStock",'
        '"seller":{"@type":"Organization","name":"americanas"}}]}'
    )

    produto = extrair_produto(html)

    assert produto.preco_avista == Decimal("10.50")
    assert produto.vendedor == "americanas"


def test_aceita_oferta_unica_fora_de_lista_e_preco_numerico():
    html = pagina_com_product(
        '{"@type":"Product","sku":"1","name":"X","offers":'
        '{"@type":"Offer","price":1299.9,"availability":"https://schema.org/InStock"}}'
    )

    produto = extrair_produto(html)

    assert produto.disponivel is True
    assert produto.preco_avista == Decimal("1299.9")


def test_produto_sem_ofertas_fica_indisponivel():
    produto = extrair_produto(pagina_com_product('{"@type":"Product","sku":"1","name":"X"}'))

    assert produto.disponivel is False


def test_pagina_sem_ld_json_e_invalida():
    with pytest.raises(PaginaInvalida):
        extrair_produto("<html><body>pagina qualquer</body></html>")


def test_pagina_sem_bloco_product_e_invalida():
    html = pagina_com_product('{"@type":"BreadcrumbList","itemListElement":[]}')
    with pytest.raises(PaginaInvalida):
        extrair_produto(html)


def test_product_sem_sku_e_invalido():
    with pytest.raises(PaginaInvalida):
        extrair_produto(pagina_com_product('{"@type":"Product","name":"X","offers":[]}'))


def test_preco_em_formato_inesperado_e_invalido():
    html = pagina_com_product(
        '{"@type":"Product","sku":"1","name":"X","offers":'
        '[{"@type":"Offer","price":"R$ 10,00","availability":"https://schema.org/InStock"}]}'
    )
    with pytest.raises(PaginaInvalida):
        extrair_produto(html)


# --- ColetorAmericanas: junta download e extração -------------------------


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
    coletor = ColetorAmericanas(
        urls=list(paginas),
        baixar=baixar,
        intervalo_segundos=2.0,
        esperar=esperas.append,
    )
    return coletor, baixar, esperas


def test_coleta_produto_em_estoque_com_loja_americanas():
    coletor, _, _ = montar({URL_EM_ESTOQUE: ler_fixture("americanas_produto_em_estoque.html")})

    itens = coletor.coletar()

    assert len(itens) == 1
    assert itens[0].produto_id == "8776497"
    assert itens[0].loja == LOJA == "americanas"
    assert itens[0].preco.valor == Decimal("901.55")


def test_ignora_produto_sem_estoque():
    coletor, _, _ = montar(
        {
            URL_EM_ESTOQUE: ler_fixture("americanas_produto_em_estoque.html"),
            URL_SEM_ESTOQUE: ler_fixture("americanas_produto_sem_estoque.html"),
        }
    )

    itens = coletor.coletar()

    assert [item.produto_id for item in itens] == ["8776497"]


def test_espera_o_intervalo_entre_requisicoes_mas_nao_antes_da_primeira():
    coletor, baixar, esperas = montar(
        {
            URL_EM_ESTOQUE: ler_fixture("americanas_produto_em_estoque.html"),
            URL_SEM_ESTOQUE: ler_fixture("americanas_produto_sem_estoque.html"),
        }
    )

    coletor.coletar()

    assert baixar.urls_pedidas == [URL_EM_ESTOQUE, URL_SEM_ESTOQUE]
    assert esperas == [2.0]


def test_falha_em_uma_pagina_nao_derruba_a_rodada():
    coletor, _, _ = montar(
        {
            "https://www.americanas.com.br/fora-do-ar/p": requests.ConnectionError("timeout"),
            "https://www.americanas.com.br/mudou-o-site/p": "<html>sem json-ld</html>",
            URL_EM_ESTOQUE: ler_fixture("americanas_produto_em_estoque.html"),
        }
    )

    itens = coletor.coletar()

    assert [item.produto_id for item in itens] == ["8776497"]
