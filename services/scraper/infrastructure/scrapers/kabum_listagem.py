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
from decimal import Decimal
from typing import Callable, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests

from application.conferencia import JaConfirmado, nada_confirmado
from application.portas import ObservacaoDeProduto, ProdutoMonitorado, ProdutoSemEstoque
from infrastructure.scrapers.base import PaginaInvalida, baixar_html, converter
from infrastructure.scrapers.kabum import (
    LOJA,
    ProdutoKabum,
    extrair_cupom,
    extrair_produto,
    ler_preco_de,
)
from infrastructure.scrapers.listagem import ColetorDeListagem, ItemDeListagem, PaginaDeListagem

TAMANHO_PAGINA = 60
_PADRAO_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

logger = logging.getLogger(__name__)


# Os formatos comuns a toda listagem, com os nomes que este módulo já usava.
ItemListagem = ItemDeListagem
ListagemKabum = PaginaDeListagem


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
    # Produto em campanha (ex.: "Esquenta Black"): os preços da campanha vêm no
    # bloco "offer", e os de fora dele são os de sem campanha. A página do
    # produto já mostra os da campanha; ler só os de fora fazia a listagem
    # parecer desatualizada.
    oferta = item.get("offer") if isinstance(item.get("offer"), dict) else {}
    preco = _primeiro(oferta.get("priceWithDiscount"), item.get("priceWithDiscount"), item.get("price"))
    if preco is None:
        return None
    preco_cartao = _primeiro(oferta.get("price"), item.get("price"))

    produto = ProdutoKabum(
        produto_id=str(codigo),
        nome=item.get("name") or "",
        preco_avista=Decimal(str(preco)),
        disponivel=bool(item.get("available")),
        cupom=extrair_cupom(item.get("stamps")),
        preco_de=ler_preco_de(item.get("oldPrice"), preco_cartao),
    )
    return ItemListagem(produto=produto, url=url_do_produto(codigo, item.get("friendlyName") or ""))


def _primeiro(*valores):
    """O primeiro valor informado (0 conta como informado; None não)."""
    return next((valor for valor in valores if valor is not None), None)


def url_do_produto(codigo, nome_amigavel: str) -> str:
    return f"https://www.kabum.com.br/produto/{codigo}/{nome_amigavel}".rstrip("/")


def url_da_pagina(url_listagem: str, numero: int) -> str:
    """Página 1 é a URL como está; as seguintes ganham page_number e page_size."""
    if numero <= 1:
        return url_listagem
    partes = urlsplit(url_listagem)
    consulta = urlencode({"page_number": numero, "page_size": TAMANHO_PAGINA})
    return urlunsplit((partes.scheme, partes.netloc, partes.path, consulta, ""))


class ColetorListagemKabum(ColetorDeListagem):
    """Percorre listagens de categoria da Kabum e devolve todos os produtos disponíveis.

    O laço das páginas e as esperas vêm de ColetorDeListagem. Aqui ficam os
    passos da Kabum: ler a página, montar a URL da página N e conferir produtos.

    A listagem não traz tudo (o percentual do cupom, por exemplo, só aparece
    na página do produto), então cada produto é conferido na própria página,
    a não ser que ja_confirmado devolva o registro anterior (por padrão, nunca
    devolve). Na rodada do bot, só se confere o que mudou desde a última coleta.
    """

    loja = LOJA

    def __init__(
        self,
        listagens: list[ProdutoMonitorado],
        baixar: Callable[[str], str] = baixar_html,
        intervalo_segundos: float = 2.0,
        esperar: Callable[[float], None] = time.sleep,
        baixar_produto: Callable[[str], str] = baixar_html,
        ja_confirmado: JaConfirmado = nada_confirmado,
    ):
        super().__init__(listagens, baixar=baixar, intervalo_segundos=intervalo_segundos,
                         esperar=esperar)
        self._baixar_produto = baixar_produto
        self._ja_confirmado = ja_confirmado

    def extrair_pagina(self, html: str) -> ListagemKabum:
        return extrair_listagem(html)

    def url_da_pagina(self, url_listagem: str, numero: int) -> str:
        return url_da_pagina(url_listagem, numero)

    def converter_pagina(self, listagem: ListagemKabum) -> list[ObservacaoDeProduto]:
        coletados = []
        conferidos = sem_mudanca = 0
        for item in listagem.itens:
            if not item.produto.disponivel:
                coletados.append(ProdutoSemEstoque(item.produto.produto_id, self.loja))
                continue
            da_listagem = converter(item.produto, item.url, self.loja, registrar_no_log=False)
            confirmado = self._ja_confirmado(da_listagem)
            if confirmado is not None:
                coletados.append(confirmado)
                sem_mudanca += 1
                continue
            conferidos += 1
            self.esperar_a_vez()
            try:
                produto = extrair_produto(self._baixar_produto(item.url))
                if produto.produto_id != item.produto.produto_id:
                    raise PaginaInvalida("a página individual retornou outro produto")
            except (requests.RequestException, PaginaInvalida, ValueError) as erro:
                logger.warning("%s: não confirmei o preço de %s: %s", self.loja, item.url, erro)
                continue
            coletados.append(converter(produto, item.url, self.loja))
        logger.info(
            "%s: %d produto(s) conferido(s) na página, %d sem mudança desde a última coleta",
            self.loja, conferidos, sem_mudanca,
        )
        return coletados
