from application.portas import PrecoColetado, ProdutoSemEstoque
from decimal import Decimal
from pathlib import Path

import pytest
import requests

from application.portas import ProdutoMonitorado
from domain.cupom import Cupom
from infrastructure.scrapers.americanas_listagem import (
    ColetorListagemAmericanas,
    extrair_listagem,
    extrair_pagina,
    url_do_produto,
)
from infrastructure.scrapers.base import PaginaInvalida

FIXTURES = Path(__file__).parent / "fixtures"
URL_LISTAGEM = "https://www.americanas.com.br/computadores-e-informatica/impressora"
URL_EPSON = (
    "https://www.americanas.com.br/impressora-epson-ecotank-l1250-tanque-de-tinta-wi-fi-usb-8297500-8776497/p"
)


def ler_fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


# --- extrair_listagem: função pura, sem rede --------------------------------


def test_extrai_produtos_da_pagina_de_categoria():
    itens = extrair_listagem(ler_fixture("americanas_listagem.html"))

    assert [i.produto.produto_id for i in itens] == ["8776497", "2542515"]

    epson = itens[0]
    assert epson.produto.nome == "Impressora Epson EcoTank L1250 Tanque de Tinta Wi-Fi Bivolt"
    assert epson.produto.preco_avista == Decimal("901.55")  # menor oferta em estoque
    assert epson.produto.vendedor == "magazineluiza"
    assert epson.produto.preco_de == Decimal("1279")
    assert epson.produto.cupom == Cupom("10DO10")
    assert epson.produto.disponivel is True
    assert epson.url == URL_EPSON


def test_produto_sem_oferta_em_estoque_fica_indisponivel():
    itens = extrair_listagem(ler_fixture("americanas_listagem.html"))

    cartucho = itens[1].produto
    assert cartucho.disponivel is False
    assert cartucho.preco_de is None
    assert cartucho.cupom is None


def test_url_do_produto():
    assert url_do_produto("abc-123") == "https://www.americanas.com.br/abc-123/p"
    assert url_do_produto("/abc-123/") == "https://www.americanas.com.br/abc-123/p"


def test_pagina_sem_listagem_e_invalida():
    with pytest.raises(PaginaInvalida):
        extrair_listagem(
            '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":{}}}}</script>'
        )
    with pytest.raises(PaginaInvalida):
        extrair_listagem("<html>sem next data</html>")


# --- ColetorListagemAmericanas: junta download e extração -------------------


class DownloadFalso:
    def __init__(self, paginas: dict[str, str]):
        self.paginas = paginas
        self.urls_pedidas: list[str] = []

    def __call__(self, url: str) -> str:
        self.urls_pedidas.append(url)
        resultado = self.paginas[url]
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def montar(paginas: dict[str, str], listagens: list[ProdutoMonitorado]):
    baixar = DownloadFalso(paginas)
    esperas: list[float] = []
    coletor = ColetorListagemAmericanas(
        listagens, baixar=baixar, intervalo_segundos=2.0, esperar=esperas.append
    )
    return coletor, baixar, esperas


def listagem(url: str = URL_LISTAGEM, paginas: int = 1) -> ProdutoMonitorado:
    return ProdutoMonitorado("americanas", url, tipo="listagem", paginas=paginas)


def test_coleta_so_os_disponiveis_com_loja_url_cupom_e_preco_de():
    coletor, _, _ = montar({URL_LISTAGEM: ler_fixture("americanas_listagem.html")}, [listagem()])

    itens = [i for i in coletor.coletar() if isinstance(i, PrecoColetado)]

    assert [i.produto_id for i in itens] == ["8776497"]
    assert itens[0].loja == "americanas"
    assert itens[0].url == URL_EPSON
    assert itens[0].preco.valor == Decimal("901.55")
    assert itens[0].preco_de.valor == Decimal("1279")
    assert itens[0].cupom == Cupom("10DO10")


def test_espera_entre_listagens_e_falha_nao_derruba_a_rodada():
    outra = "https://www.americanas.com.br/computadores-e-informatica/notebook"
    coletor, baixar, esperas = montar(
        {
            outra: requests.ConnectionError("timeout"),
            URL_LISTAGEM: ler_fixture("americanas_listagem.html"),
        },
        [listagem(outra), listagem()],
    )

    itens = [i for i in coletor.coletar() if isinstance(i, PrecoColetado)]

    assert [i.produto_id for i in itens] == ["8776497"]
    assert baixar.urls_pedidas == [outra, URL_LISTAGEM]
    assert esperas == [2.0]


def test_pagina_informa_quantas_paginas_a_categoria_tem():
    pagina = extrair_pagina(ler_fixture("americanas_listagem.html"))

    # A fixture traz 2 produtos na página e "totalCount": 33 na categoria.
    assert (pagina.pagina_atual, pagina.total_paginas) == (1, 17)
    assert pagina.tem_proxima


def test_pedir_mais_paginas_le_so_a_primeira_e_avisa(caplog):
    coletor, baixar, esperas = montar(
        {URL_LISTAGEM: ler_fixture("americanas_listagem.html")}, [listagem(paginas=3)])

    itens = [i for i in coletor.coletar() if isinstance(i, PrecoColetado)]

    assert [i.produto_id for i in itens] == ["8776497"]
    assert baixar.urls_pedidas == [URL_LISTAGEM]
    assert esperas == []
    assert "não sei abrir a página 2" in caplog.text


def test_com_uma_pagina_configurada_nao_ha_aviso(caplog):
    coletor, _, _ = montar({URL_LISTAGEM: ler_fixture("americanas_listagem.html")}, [listagem()])

    coletor.coletar()

    assert "não sei abrir" not in caplog.text
