"""Coletor de listagem da Kabum: lê 60 produtos de uma vez numa página de categoria.

Uma página como /hardware/placa-de-video-vga embute, no __NEXT_DATA__, o
mesmo JSON que a API de catálogo da loja devolve: código, nome, preços,
disponibilidade e selo de cupom de cada produto. Uma única requisição
substitui sessenta visitas a páginas de produto.

A página seguinte é ?page_number=2 (sem ordenação: o robots.txt da loja
proíbe os parâmetros sort=...). Quantas páginas seguir é configurado por
listagem no produtos.json, campo "paginas".
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests

from application.portas import ColetorDePrecos, PrecoColetado, ProdutoMonitorado
from infrastructure.scrapers.base import PaginaInvalida, baixar_html, converter
from infrastructure.scrapers.kabum import (
    LOJA,
    ProdutoKabum,
    extrair_cupom,
    ler_preco_de,
)

TAMANHO_PAGINA = 60
_PADRAO_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ItemListagem:
    produto: ProdutoKabum
    url: str


@dataclass(frozen=True)
class ListagemKabum:
    itens: list[ItemListagem]
    pagina_atual: int
    total_paginas: int

    @property
    def tem_proxima(self) -> bool:
        return self.pagina_atual < self.total_paginas


def extrair_listagem(html: str) -> ListagemKabum:
    """Função pura: lê os produtos e a paginação de uma página de categoria."""
    encontrado = _PADRAO_NEXT_DATA.search(html)
    if encontrado is None:
        raise PaginaInvalida("não encontrei o bloco __NEXT_DATA__ na página")

    dados = json.loads(encontrado.group(1))
    conteudo = dados.get("props", {}).get("pageProps", {}).get("data")
    # A Kabum embute o catálogo como uma string JSON dentro do JSON da página.
    if isinstance(conteudo, str):
        conteudo = json.loads(conteudo, parse_float=Decimal)
    catalogo = (conteudo or {}).get("catalogServer") if isinstance(conteudo, dict) else None
    if not isinstance(catalogo, dict) or not isinstance(catalogo.get("data"), list):
        raise PaginaInvalida("a página não contém uma listagem de produtos")

    itens = [_converter_item(item) for item in catalogo["data"] if isinstance(item, dict)]
    paginacao = catalogo.get("pagination") or {}
    return ListagemKabum(
        itens=[item for item in itens if item is not None],
        pagina_atual=int(paginacao.get("current") or 1),
        total_paginas=int(paginacao.get("total") or 1),
    )


def _converter_item(item: dict) -> Optional[ItemListagem]:
    codigo = item.get("code")
    if codigo is None:
        return None
    preco = item.get("priceWithDiscount")
    if preco is None:
        preco = item.get("price")
    if preco is None:
        return None

    produto = ProdutoKabum(
        produto_id=str(codigo),
        nome=item.get("name") or "",
        preco_avista=Decimal(str(preco)),
        disponivel=bool(item.get("available")),
        cupom=extrair_cupom(item.get("stamps")),
        preco_de=ler_preco_de(item.get("oldPrice")),
    )
    return ItemListagem(produto=produto, url=url_do_produto(codigo, item.get("friendlyName") or ""))


def url_do_produto(codigo, nome_amigavel: str) -> str:
    return f"https://www.kabum.com.br/produto/{codigo}/{nome_amigavel}".rstrip("/")


def url_da_pagina(url_listagem: str, numero: int) -> str:
    """Página 1 é a URL como está; as seguintes ganham page_number e page_size."""
    if numero <= 1:
        return url_listagem
    partes = urlsplit(url_listagem)
    consulta = urlencode({"page_number": numero, "page_size": TAMANHO_PAGINA})
    return urlunsplit((partes.scheme, partes.netloc, partes.path, consulta, ""))


class ColetorListagemKabum(ColetorDePrecos):
    """Percorre listagens de categoria da Kabum e devolve todos os produtos disponíveis."""

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
        primeira_requisicao = True

        for listagem in self.listagens:
            numero = 1
            while numero <= max(1, listagem.paginas):
                if not primeira_requisicao and self._intervalo > 0:
                    self._esperar(self._intervalo)
                primeira_requisicao = False

                pagina = self._coletar_pagina(url_da_pagina(listagem.url, numero))
                if pagina is None:
                    break
                coletados.extend(self._converter(pagina))
                if not pagina.tem_proxima:
                    break
                numero += 1

        return coletados

    def _coletar_pagina(self, url: str) -> Optional[ListagemKabum]:
        try:
            listagem = extrair_listagem(self._baixar(url))
        except (requests.RequestException, PaginaInvalida, ValueError) as erro:
            logger.warning("%s: falha ao coletar a listagem %s: %s", self.loja, url, erro)
            return None
        logger.info(
            "%s: listagem %s, página %d de %d, %d produto(s)",
            self.loja, url, listagem.pagina_atual, listagem.total_paginas, len(listagem.itens),
        )
        return listagem

    def _converter(self, listagem: ListagemKabum) -> list[PrecoColetado]:
        itens = (converter(item.produto, item.url, self.loja) for item in listagem.itens)
        return [item for item in itens if item is not None]
