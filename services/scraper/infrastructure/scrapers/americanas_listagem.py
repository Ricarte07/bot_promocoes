"""Vai ler os Produtos de uma pagina de categoria
Ele pega uma pagina de categoria e vai embutir no __NEXT_DATA__, sendo 12 por vez e trazendo as informações de slug
,nome, as ofertas,preço, e a coleçao de cupons.

"""

import json
import math
import re
from decimal import Decimal
from typing import Optional

from infrastructure.scrapers.americanas import (
    LOJA,
    ProdutoAmericanas,
    extrair_cupom,
    ler_preco,
)
from infrastructure.scrapers.base import PaginaInvalida
from infrastructure.scrapers.listagem import ColetorDeListagem, ItemDeListagem, PaginaDeListagem

_PADRAO_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_EM_ESTOQUE = "https://schema.org/InStock"
_SUFIXO_NOME = " | Americanas"



ItemListagem = ItemDeListagem  # nome que este módulo já usava


def extrair_listagem(html: str) -> list[ItemListagem]:
    """Função pura: lê os produtos de uma página de categoria."""
    return extrair_pagina(html).itens


def extrair_pagina(html: str) -> PaginaDeListagem:
    """Função pura: lê os produtos e quantas páginas a categoria tem."""
    encontrado = _PADRAO_NEXT_DATA.search(html)
    if encontrado is None:
        raise PaginaInvalida("não encontrei o bloco __NEXT_DATA__ na página")

    dados = json.loads(encontrado.group(1), parse_float=Decimal)
    conteudo = ((dados.get("props") or {}).get("pageProps") or {}).get("data") or {}
    arestas = (((conteudo.get("search") or {}).get("products")) or {}).get("edges")
    if not isinstance(arestas, list):
        raise PaginaInvalida("a página não contém uma listagem de produtos")

    itens = []
    for aresta in arestas:
        item = _converter_item((aresta or {}).get("node") or {})
        if item is not None:
            itens.append(item)

    total = ((conteudo["search"]["products"].get("pageInfo") or {}).get("totalCount")) or 0
    por_pagina = len(arestas) or 1
    return PaginaDeListagem(itens=itens, pagina_atual=1,
                            total_paginas=max(1, math.ceil(int(total) / por_pagina)))


def _converter_item(no: dict) -> Optional[ItemListagem]:
    sku = no.get("sku")
    slug = no.get("slug")
    if not sku or not slug:
        return None

    nome = str(no.get("name") or "").removesuffix(_SUFIXO_NOME).strip()
    cupom = extrair_cupom(no)
    melhor = _melhor_oferta(no)

    if melhor is None:
        produto = ProdutoAmericanas(
            produto_id=str(sku),
            nome=nome,
            preco_avista=Decimal("0"),
            disponivel=False,
            vendedor="",
            cupom=cupom,
        )
    else:
        preco, preco_de, vendedor = melhor
        produto = ProdutoAmericanas(
            produto_id=str(sku),
            nome=nome,
            preco_avista=preco,
            disponivel=True,
            vendedor=vendedor,
            cupom=cupom,
            preco_de=preco_de,
        )
    return ItemListagem(produto=produto, url=url_do_produto(slug))


def _melhor_oferta(no: dict) -> Optional[tuple[Decimal, Optional[Decimal], str]]:
    """Entre as ofertas em estoque, a de menor preço: (preço, preço "de" ou None, vendedor)."""
    melhor = None
    for oferta in ((no.get("offers") or {}).get("offers")) or []:
        oferta = oferta or {}
        if oferta.get("availability") != _EM_ESTOQUE:
            continue
        preco = ler_preco(oferta.get("price"))
        if preco <= 0:
            continue
        if melhor is None or preco < melhor[0]:
            lista = ler_preco(oferta.get("listPrice"))
            vendedor = str((oferta.get("seller") or {}).get("identifier") or "")
            melhor = (preco, lista if lista > preco else None, vendedor)
    return melhor


def url_do_produto(slug: str) -> str:
    return f"https://www.americanas.com.br/{slug.strip('/')}/p"


class ColetorListagemAmericanas(ColetorDeListagem):
    """Percorre listagens de categoria da Americanas e devolve os produtos.

    O laço das páginas e as esperas vêm de ColetorDeListagem. A Americanas só
    entrega pronta a primeira página: as seguintes chegam ao navegador por uma
    API à parte, e a URL ignora ?page=N. Por isso url_da_pagina fica com o
    padrão (só a primeira), e uma listagem com "paginas" maior que 1 avisa no
    log quantas páginas ficaram de fora, em vez de ignorar a configuração calada.
    """

    loja = LOJA

    def extrair_pagina(self, html: str) -> PaginaDeListagem:
        return extrair_pagina(html)
