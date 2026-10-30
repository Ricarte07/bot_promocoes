"""Adaptador da loja Americanas para a porta ColetorDePrecos.

A página de produto da Americanas publica os dados em blocos
<script type="application/ld+json"> no padrão schema.org. O bloco de
@type "Product" traz o sku e uma lista de ofertas, uma por vendedor
(a própria Americanas e lojistas do marketplace), cada uma com preço e
disponibilidade. Quando o produto está esgotado, a única oferta vem com
preço "0" e availability OutOfStock.

O cupom não está no JSON-LD. Ele aparece no bloco __NEXT_DATA__, na lista de
coleções do produto (clusterHighlights): uma coleção chamada "cupom10do10"
significa que o cupom 10DO10 vale para o item. A página não diz quanto o
cupom desconta, por isso o percentual fica desconhecido.

extrair_produto(html) é uma função pura, sem rede. O laço de URLs, o
intervalo e o tratamento de erro vêm de ColetorPorUrls.
"""

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator, Optional

from domain.cupom import Cupom
from infrastructure.scrapers.base import ColetorPorUrls, PaginaInvalida, ProdutoExtraido

__all__ = ["LOJA", "ColetorAmericanas", "PaginaInvalida", "ProdutoAmericanas", "extrair_produto"]

LOJA = "americanas"

_PADRAO_LD_JSON = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
_PADRAO_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_EM_ESTOQUE = "https://schema.org/InStock"
_SUFIXO_NOME = " | Americanas"
_PREFIXO_COLECAO_CUPOM = "cupom"


@dataclass(frozen=True)
class ProdutoAmericanas(ProdutoExtraido):
    """Dados crus de um produto, como a Americanas os entrega.

    vendedor é quem oferece o preço escolhido (a Americanas ou um lojista do
    marketplace). Fica vazio quando não há oferta disponível.
    """

    vendedor: str


def extrair_produto(html: str) -> ProdutoAmericanas:
    """Função pura: lê o bloco JSON-LD de Product e devolve o produto.

    Entre as ofertas em estoque, escolhe a de menor preço: é o valor que
    o comprador vê como "a partir de" na página.
    """
    produto = _localizar_produto(html)
    cupom = _extrair_cupom(html)

    sku = produto.get("sku")
    if not sku:
        raise PaginaInvalida("o bloco Product não informa o sku")

    nome = str(produto.get("name") or "").removesuffix(_SUFIXO_NOME).strip()

    ofertas = produto.get("offers") or []
    if isinstance(ofertas, dict):
        ofertas = [ofertas]

    disponiveis = [
        (preco, oferta)
        for oferta in ofertas
        if oferta.get("availability") == _EM_ESTOQUE
        and (preco := _ler_preco(oferta.get("price"))) > 0
    ]
    if not disponiveis:
        return ProdutoAmericanas(
            produto_id=str(sku),
            nome=nome,
            preco_avista=Decimal("0"),
            disponivel=False,
            vendedor="",
            cupom=cupom,
        )

    menor_preco, melhor_oferta = min(disponiveis, key=lambda par: par[0])
    vendedor = (melhor_oferta.get("seller") or {}).get("name") or ""

    return ProdutoAmericanas(
        produto_id=str(sku),
        nome=nome,
        preco_avista=menor_preco,
        disponivel=True,
        vendedor=str(vendedor),
        cupom=cupom,
    )


def _blocos_ld_json(html: str) -> Iterator[Any]:
    """Percorre todos os blocos JSON-LD da página, ignorando os que não são JSON válido."""
    for encontrado in _PADRAO_LD_JSON.finditer(html):
        try:
            dados = json.loads(encontrado.group(1), parse_float=Decimal)
        except json.JSONDecodeError:
            continue
        # Um bloco pode ter um único objeto ou uma lista deles.
        yield from dados if isinstance(dados, list) else [dados]


def _localizar_produto(html: str) -> dict:
    """Devolve o bloco JSON-LD cujo @type é Product (a página também tem BreadcrumbList etc.)."""
    encontrou_algum = False
    for bloco in _blocos_ld_json(html):
        encontrou_algum = True
        if not isinstance(bloco, dict):
            continue
        tipo = bloco.get("@type")
        tipos = tipo if isinstance(tipo, list) else [tipo]
        if "Product" in tipos:
            return bloco

    if not encontrou_algum:
        raise PaginaInvalida("não encontrei nenhum bloco JSON-LD na página")
    raise PaginaInvalida("a página não contém um bloco Product")


def _extrair_cupom(html: str) -> Optional[Cupom]:
    """Procura, nas coleções do produto dentro do __NEXT_DATA__, uma chamada "cupom<CÓDIGO>".

    Página sem __NEXT_DATA__ ou sem coleções simplesmente não tem cupom: não é erro.
    """
    encontrado = _PADRAO_NEXT_DATA.search(html)
    if encontrado is None:
        return None
    try:
        dados = json.loads(encontrado.group(1))
    except json.JSONDecodeError:
        return None

    produto = (
        ((dados.get("props") or {}).get("pageProps") or {}).get("data") or {}
    ).get("product") or {}
    for colecao in produto.get("clusterHighlights") or []:
        nome = str((colecao or {}).get("name") or "")
        if nome.lower().startswith(_PREFIXO_COLECAO_CUPOM):
            codigo = nome[len(_PREFIXO_COLECAO_CUPOM):].strip(" -_").upper()
            if codigo:
                return Cupom(codigo)
    return None


def _ler_preco(valor: Any) -> Decimal:
    """Converte o preço do JSON-LD (texto como "949.90" ou número) em Decimal."""
    if valor is None:
        return Decimal("0")
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        raise PaginaInvalida(f"preço em formato inesperado: {valor!r}")


class ColetorAmericanas(ColetorPorUrls):
    """Monitora uma lista fixa de URLs de produto da Americanas.

    O robots.txt da loja libera as páginas de produto (/.../p) e proíbe só
    áreas como carrinho, conta e checkout, que não visitamos.
    """

    loja = LOJA

    def extrair(self, html: str) -> ProdutoAmericanas:
        return extrair_produto(html)
