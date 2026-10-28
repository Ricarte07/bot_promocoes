"""Adaptador da loja Kabum para a porta ColetorDePrecos.

A página de produto da Kabum é Next.js e embute um JSON __NEXT_DATA__ com
todos os dados do produto. extrair_produto(html) lê só esse bloco: é uma
função pura, sem rede, testável com um HTML de exemplo.

O laço de URLs, o intervalo entre requisições e o tratamento de erro vêm de
ColetorPorUrls (infrastructure/scrapers/base.py).
"""

import json
import re
from dataclasses import dataclass
from decimal import Decimal

from infrastructure.scrapers.base import ColetorPorUrls, PaginaInvalida, ProdutoExtraido

__all__ = ["LOJA", "ColetorKabum", "PaginaInvalida", "ProdutoKabum", "extrair_produto"]

LOJA = "kabum"

_PADRAO_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


@dataclass(frozen=True)
class ProdutoKabum(ProdutoExtraido):
    """Dados crus de um produto, como a Kabum os entrega."""


def extrair_produto(html: str) -> ProdutoKabum:
    """Função pura: lê o JSON __NEXT_DATA__ embutido na página e devolve o produto.

    Usa parse_float=Decimal para que o valor 1569.99 nunca vire float.
    """
    encontrado = _PADRAO_NEXT_DATA.search(html)
    if encontrado is None:
        raise PaginaInvalida("não encontrei o bloco __NEXT_DATA__ na página")

    dados = json.loads(encontrado.group(1), parse_float=Decimal)
    produto = dados.get("props", {}).get("pageProps", {}).get("product")
    if not produto:
        raise PaginaInvalida("a página não contém um produto")

    precos = produto.get("prices") or {}
    preco_avista = precos.get("priceWithDiscount")
    if preco_avista is None:
        preco_avista = produto.get("price")
    if preco_avista is None:
        raise PaginaInvalida("a página não informa o preço do produto")

    return ProdutoKabum(
        produto_id=str(produto["id"]),
        nome=produto.get("title") or "",
        preco_avista=Decimal(preco_avista),
        disponivel=bool(produto.get("available")),
    )


class ColetorKabum(ColetorPorUrls):
    """Monitora uma lista fixa de URLs de produto da Kabum.

    O robots.txt da loja permite /produto/..., mas proíbe a busca com parâmetros,
    por isso não varremos a loja: só visitamos os produtos escolhidos.
    """

    loja = LOJA

    def extrair(self, html: str) -> ProdutoKabum:
        return extrair_produto(html)
