"""Adaptador da loja Kabum para a porta ColetorDePrecos.

Duas responsabilidades separadas de propósito:
- extrair_produto(html): função pura, sem rede, testável com um HTML de exemplo.
- baixar_html(url): a única parte que fala com a internet.

ColetorKabum junta as duas e recebe a função de download no construtor,
para que os testes possam injetar uma versão falsa.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

import requests

from application.portas import ColetorDePrecos, PrecoColetado
from domain.preco import Preco

LOJA = "kabum"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
_PADRAO_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

logger = logging.getLogger(__name__)


class PaginaInvalida(ValueError):
    """O HTML recebido não tem o formato esperado de uma página de produto da Kabum."""


@dataclass(frozen=True)
class ProdutoKabum:
    """Dados crus de um produto, como a Kabum os entrega. Ainda não é domínio."""

    produto_id: str
    nome: str
    preco_avista: Decimal
    disponivel: bool


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


def baixar_html(url: str, timeout: float = 15.0) -> str:
    """Faz uma única requisição HTTP e devolve o HTML como texto."""
    resposta = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout)
    resposta.raise_for_status()
    return resposta.text


class ColetorKabum(ColetorDePrecos):
    """Monitora uma lista fixa de URLs de produto da Kabum.

    O robots.txt da loja permite /produto/..., mas proíbe a busca com parâmetros,
    por isso não varremos a loja: só visitamos os produtos escolhidos.
    """

    def __init__(
        self,
        urls: list[str],
        baixar: Callable[[str], str] = baixar_html,
        intervalo_segundos: float = 2.0,
        esperar: Callable[[float], None] = time.sleep,
    ):
        self.urls = list(urls)
        self._baixar = baixar
        self._intervalo = intervalo_segundos
        self._esperar = esperar

    def coletar(self) -> list[PrecoColetado]:
        coletados: list[PrecoColetado] = []

        for posicao, url in enumerate(self.urls):
            if posicao > 0 and self._intervalo > 0:
                self._esperar(self._intervalo)

            item = self._coletar_um(url)
            if item is not None:
                coletados.append(item)

        return coletados

    def _coletar_um(self, url: str) -> Optional[PrecoColetado]:
        try:
            produto = extrair_produto(self._baixar(url))
        except (requests.RequestException, PaginaInvalida) as erro:
            # Uma página com problema não pode derrubar a rodada inteira.
            logger.warning("Kabum: falha ao coletar %s: %s", url, erro)
            return None

        if not produto.disponivel:
            logger.info("Kabum: produto %s sem estoque, ignorado", produto.produto_id)
            return None

        logger.info(
            "Kabum: produto %s a R$ %s (%s)", produto.produto_id, produto.preco_avista, produto.nome[:50]
        )
        return PrecoColetado(
            produto_id=produto.produto_id,
            loja=LOJA,
            preco=Preco(produto.preco_avista),
        )
