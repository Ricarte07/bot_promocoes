"""O que todo scraper de loja tem em comum.

Cada loja muda só na extração (como ler o preço do HTML dela). O resto, visitar
uma lista fixa de URLs, esperar entre requisições e não deixar uma página com
problema derrubar a rodada, vive aqui, em ColetorPorUrls.

Para adicionar uma loja:
1. escreva uma função pura extrair_produto(html) -> ProdutoExtraido;
2. crie uma subclasse de ColetorPorUrls com `loja` e `extrair` definidos;
3. registre a fábrica em interfaces/agendador.py.
"""

import logging
import time
from abc import abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

import requests

from application.portas import ColetorDePrecos, PrecoColetado
from domain.preco import Preco

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

logger = logging.getLogger(__name__)


class PaginaInvalida(ValueError):
    """O HTML recebido não tem o formato esperado de uma página de produto."""


@dataclass(frozen=True)
class ProdutoExtraido:
    """Dados crus de um produto, como a loja os entrega. Ainda não é domínio."""

    produto_id: str
    nome: str
    preco_avista: Decimal
    disponivel: bool


def baixar_html(url: str, timeout: float = 15.0) -> str:
    """Faz uma única requisição HTTP e devolve o HTML como texto."""
    resposta = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout)
    resposta.raise_for_status()
    return resposta.text


class ColetorPorUrls(ColetorDePrecos):
    """Monitora uma lista fixa de URLs de produto de uma loja.

    Recebe a função de download no construtor para que os testes possam
    injetar uma versão falsa, sem rede.
    """

    loja: str  # cada subclasse define o nome da loja

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

    @abstractmethod
    def extrair(self, html: str) -> ProdutoExtraido:
        """Lê o HTML da loja e devolve o produto. Deve lançar PaginaInvalida se não conseguir."""

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
            produto = self.extrair(self._baixar(url))
        except (requests.RequestException, PaginaInvalida) as erro:
            # Uma página com problema não pode derrubar a rodada inteira.
            logger.warning("%s: falha ao coletar %s: %s", self.loja, url, erro)
            return None

        if not produto.disponivel:
            logger.info("%s: produto %s sem estoque, ignorado", self.loja, produto.produto_id)
            return None

        logger.info(
            "%s: produto %s a R$ %s (%s)",
            self.loja,
            produto.produto_id,
            produto.preco_avista,
            produto.nome[:50],
        )
        return PrecoColetado(
            produto_id=produto.produto_id,
            loja=self.loja,
            preco=Preco(produto.preco_avista),
            nome=produto.nome,
            url=url,
        )
