import json
from decimal import Decimal
from pathlib import Path

import pytest
import requests

from application.portas import ProdutoMonitorado
from domain.cupom import Cupom
from infrastructure.scrapers.base import PaginaInvalida
from infrastructure.scrapers.kabum_listagem import (
    ColetorListagemKabum,
    extrair_listagem,
    url_da_pagina,
)

FIXTURES = Path(__file__).parent / "fixtures"
URL_LISTAGEM = "https://www.kabum.com.br/hardware/placa-de-video-vga"


def ler_fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def pagina_de_listagem(itens: list[dict], atual: int = 1, total: int = 1) -> str:
    """Monta uma página de categoria com o catálogo embutido como string JSON, como a Kabum faz."""
    catalogo = {"catalogServer": {"data": itens, "pagination": {"current": atual, "total": total}}}
    pagina = {"props": {"pageProps": {"data": json.dumps(catalogo)}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(pagina)}</script>'


def item(codigo: int, preco: str, disponivel: bool = True) -> dict:
    return {
        "code": codigo,
        "name": f"Produto {codigo}",
        "friendlyName": f"produto-{codigo}",
        "price": preco,
        "priceWithDiscount": preco,
        "oldPrice": 0,
        "available": disponivel,
    }


# --- extrair_listagem: função pura, sem rede --------------------------------


def test_extrai_produtos_da_pagina_de_categoria():
    listagem = extrair_listagem(ler_fixture("kabum_listagem.html"))

    assert (listagem.pagina_atual, listagem.total_paginas, listagem.tem_proxima) == (1, 8, True)
    assert [i.produto.produto_id for i in listagem.itens] == ["996572", "694714", "475651"]

    husky = listagem.itens[0]
    assert husky.produto.preco_avista == Decimal("2999.99")
    assert husky.produto.preco_de == Decimal("3529.4")
    assert husky.produto.disponivel is True
    assert husky.produto.cupom is None
    assert husky.url == (
        "https://www.kabum.com.br/produto/996572/placa-de-video-husky-alpha-rtx-3060-nvidia-12gb-gddr6"
    )


def test_item_com_selo_de_cupom_e_item_esgotado():
    listagem = extrair_listagem(ler_fixture("kabum_listagem.html"))

    asrock = listagem.itens[1].produto
    assert asrock.cupom == Cupom("ZAFADINHO10", Decimal("10"))
    assert asrock.preco_de == Decimal("8235.28")

    gigabyte = listagem.itens[2].produto
    assert gigabyte.disponivel is False
    assert gigabyte.preco_de is None


def test_ultima_pagina_nao_tem_proxima():
    listagem = extrair_listagem(pagina_de_listagem([item(1, "10")], atual=3, total=3))
    assert listagem.tem_proxima is False


def test_item_sem_codigo_ou_sem_preco_e_ignorado():
    listagem = extrair_listagem(
        pagina_de_listagem([{"name": "sem código", "price": 10}, {"code": 2, "name": "sem preço"}, item(3, "30")])
    )
    assert [i.produto.produto_id for i in listagem.itens] == ["3"]


def test_pagina_sem_catalogo_e_invalida():
    with pytest.raises(PaginaInvalida):
        extrair_listagem('<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>')
    with pytest.raises(PaginaInvalida):
        extrair_listagem("<html>sem next data</html>")


def test_url_da_pagina():
    assert url_da_pagina(URL_LISTAGEM, 1) == URL_LISTAGEM
    assert url_da_pagina(URL_LISTAGEM, 2) == URL_LISTAGEM + "?page_number=2&page_size=60"
    assert url_da_pagina(URL_LISTAGEM + "?x=1", 3) == URL_LISTAGEM + "?page_number=3&page_size=60"


# --- ColetorListagemKabum: junta download e extração ------------------------


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
    coletor = ColetorListagemKabum(listagens, baixar=baixar, intervalo_segundos=2.0, esperar=esperas.append)
    return coletor, baixar, esperas


def listagem(url: str = URL_LISTAGEM, paginas: int = 1) -> ProdutoMonitorado:
    return ProdutoMonitorado("kabum", url, tipo="listagem", paginas=paginas)


def test_coleta_so_os_disponiveis_com_loja_url_e_cupom():
    coletor, _, _ = montar({URL_LISTAGEM: ler_fixture("kabum_listagem.html")}, [listagem()])

    itens = coletor.coletar()

    assert [i.produto_id for i in itens] == ["996572", "694714"]
    assert itens[0].loja == "kabum"
    assert itens[0].url.endswith("/produto/996572/placa-de-video-husky-alpha-rtx-3060-nvidia-12gb-gddr6")
    assert itens[0].preco_de.valor == Decimal("3529.4")
    assert itens[1].cupom == Cupom("ZAFADINHO10", Decimal("10"))


def test_segue_paginas_ate_o_limite_configurado_e_espera_entre_elas():
    paginas = {
        URL_LISTAGEM: pagina_de_listagem([item(1, "10")], atual=1, total=3),
        URL_LISTAGEM + "?page_number=2&page_size=60": pagina_de_listagem([item(2, "20")], atual=2, total=3),
        URL_LISTAGEM + "?page_number=3&page_size=60": pagina_de_listagem([item(3, "30")], atual=3, total=3),
    }
    coletor, baixar, esperas = montar(paginas, [listagem(paginas=2)])

    itens = coletor.coletar()

    assert [i.produto_id for i in itens] == ["1", "2"]
    assert baixar.urls_pedidas == [URL_LISTAGEM, URL_LISTAGEM + "?page_number=2&page_size=60"]
    assert esperas == [2.0]


def test_para_na_ultima_pagina_mesmo_com_limite_maior():
    coletor, baixar, _ = montar({URL_LISTAGEM: pagina_de_listagem([item(1, "10")], atual=1, total=1)}, [listagem(paginas=5)])

    coletor.coletar()

    assert baixar.urls_pedidas == [URL_LISTAGEM]


def test_falha_em_uma_listagem_nao_derruba_a_rodada():
    outra = "https://www.kabum.com.br/hardware/fontes"
    coletor, _, _ = montar(
        {
            outra: requests.ConnectionError("timeout"),
            URL_LISTAGEM: pagina_de_listagem([item(1, "10")]),
        },
        [listagem(outra), listagem()],
    )

    assert [i.produto_id for i in coletor.coletar()] == ["1"]
