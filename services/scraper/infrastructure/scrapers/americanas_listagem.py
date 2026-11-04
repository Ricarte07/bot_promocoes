"""Vai ler os Produtos de uma pagina de categoria
Ele pega uma pagina de categoria e vai embutir no __NEXT_DATA__, sendo 12 por vez e trazendo as informações de slug
,nome, as ofertas,preço, e a coleçao de cupons.

"""

import json
import logging
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

import requests

from application.portas import ColetorDePrecos, PrecoColetado, ProdutoMonitorado
from infrastructure.scrapers.americanas import (
    LOJA,
    ProdutoAmericanas,
    extrair_cupom,
    ler_preco,
)
from infrastructure.scrapers.base import PaginaInvalida, baixar_html, converter

_PADRAO_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_EM_ESTOQUE = "https://schema.org/InStock"
_SUFIXO_NOME = " | Americanas"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ItemListagem:
    produto: ProdutoAmericanas
    url: str


def extrair_listagem(html: str) -> list[ItemListagem]:
    """Função pura: lê os produtos de uma página de categoria."""
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
    return itens


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


class ColetorListagemAmericanas(ColetorDePrecos):
    """Percorre listagens de categoria da Americanas e devolve os produtos disponíveis."""

    loja = LOJA

    def __init__(
        self,
        listagens: list[ProdutoMonitorado],
        baixar: Callable[[str], str] = baixar_html,
        intervalo_segundos: float = 2.0,
        esperar: Callable[[float], None] = time.sleep,
    ):
        self.listagens = list(listagens)
        self._baixar = baixar
        self._intervalo = intervalo_segundos
        self._esperar = esperar

    def coletar(self) -> list[PrecoColetado]:
        coletados: list[PrecoColetado] = []

        for posicao, listagem in enumerate(self.listagens):
            if posicao > 0 and self._intervalo > 0:
                self._esperar(self._intervalo)

            try:
                itens = extrair_listagem(self._baixar(listagem.url))
            except (requests.RequestException, PaginaInvalida, ValueError) as erro:
                logger.warning("%s: falha ao coletar a listagem %s: %s", self.loja, listagem.url, erro)
                continue

            logger.info("%s: listagem %s, %d produto(s)", self.loja, listagem.url, len(itens))
            for item in itens:
                coletado = converter(item.produto, item.url, self.loja)
                if coletado is not None:
                    coletados.append(coletado)

        return coletados