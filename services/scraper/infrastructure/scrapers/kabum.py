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
from typing import Any, Optional

from domain.cupom import Cupom
from infrastructure.scrapers.base import ColetorPorUrls, PaginaInvalida, ProdutoExtraido

__all__ = [
    "LOJA",
    "ColetorKabum",
    "PaginaInvalida",
    "ProdutoKabum",
    "extrair_cupom",
    "extrair_produto",
    "ler_preco_de",
]

LOJA = "kabum"

_PADRAO_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
# Selo de cupom: título "CUPOM ESQUENTA", descrição "Use o cupom ESQUENTA e ganhe 5% OFF neste item".
_PADRAO_CODIGO_CUPOM = re.compile(r"\bcupom\s+([A-Z0-9][A-Z0-9_-]*)", re.I)
_PADRAO_PERCENTUAL_OFF = re.compile(r"(\d+(?:[.,]\d+)?)\s*%\s*OFF", re.I)


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
        cupom=extrair_cupom(produto.get("stamps")),
        preco_de=ler_preco_de(precos.get("oldPrice")),
    )


def ler_preco_de(valor: Any) -> Optional[Decimal]:
    """O "de" da Kabum é prices.oldPrice; vem 0 quando não há desconto anunciado."""
    if valor is None:
        return None
    preco = Decimal(valor)
    return preco if preco > 0 else None


def extrair_cupom(selo: Any) -> Optional[Cupom]:
    """Lê o selo (stamps) que a Kabum mostra na página quando há cupom para o item.

    Selos de outro tipo, sem a palavra "cupom", são ignorados. Se o texto
    anuncia o código mas não a porcentagem, o cupom fica sem valor conhecido.
    """
    if not isinstance(selo, dict):
        return None

    texto = f"{selo.get('title') or ''} {selo.get('description') or ''}"
    codigo = _PADRAO_CODIGO_CUPOM.search(texto)
    if codigo is None:
        return None

    desconto = None
    percentual = _PADRAO_PERCENTUAL_OFF.search(texto)
    if percentual is not None:
        valor = Decimal(percentual.group(1).replace(",", "."))
        if 0 < valor < 100:
            desconto = valor

    return Cupom(codigo.group(1).upper(), desconto)


class ColetorKabum(ColetorPorUrls):
    """Monitora uma lista fixa de URLs de produto da Kabum.

    O robots.txt da loja permite /produto/..., mas proíbe a busca com parâmetros,
    por isso não varremos a loja: só visitamos os produtos escolhidos.
    """

    loja = LOJA

    def extrair(self, html: str) -> ProdutoKabum:
        return extrair_produto(html)
