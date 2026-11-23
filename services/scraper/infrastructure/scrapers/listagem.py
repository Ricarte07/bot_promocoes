"""O que toda listagem de categoria tem em comum (Template Method).

Percorrer as listagens configuradas, seguir as páginas até o limite "paginas"
do produtos.json, esperar entre requisições e não deixar uma página com
problema derrubar a rodada: isso vive aqui, em ColetorDeListagem.coletar.

Cada loja muda só nos passos:
- extrair_pagina(html): lê os produtos e a paginação de uma página (obrigatório);
- url_da_pagina(url, numero): como abrir a página N (padrão: só a primeira);
- converter_pagina(pagina): o que fazer com os produtos lidos (padrão: converter
  cada um; a Kabum confere na página do produto o que mudou).

Para adicionar a listagem de uma loja: escreva a função pura que lê a página,
crie uma subclasse com `loja` e `extrair_pagina`, e registre a fábrica em
interfaces/agendador.py.
"""

import logging
import time
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from application.portas import ColetorDePrecos, ObservacaoDeProduto, ProdutoMonitorado
from infrastructure.scrapers.base import PaginaInvalida, ProdutoExtraido, baixar_html, converter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ItemDeListagem:
    produto: ProdutoExtraido
    url: str


@dataclass(frozen=True)
class PaginaDeListagem:
    itens: list[ItemDeListagem]
    pagina_atual: int = 1
    total_paginas: int = 1

    @property
    def tem_proxima(self) -> bool:
        return self.pagina_atual < self.total_paginas


class ColetorDeListagem(ColetorDePrecos):
    loja: str  # cada subclasse define o nome da loja

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
        self._primeira_requisicao = True

    def coletar(self) -> list[ObservacaoDeProduto]:
        coletados: list[ObservacaoDeProduto] = []
        self._primeira_requisicao = True

        for listagem in self.listagens:
            numero = 1
            while numero <= max(1, listagem.paginas):
                url = self.url_da_pagina(listagem.url, numero)
                if url is None:
                    logger.warning(
                        "%s: não sei abrir a página %d de %s; só a(s) %d primeira(s) foi(ram) lida(s)",
                        self.loja, numero, listagem.url, numero - 1,
                    )
                    break
                self.esperar_a_vez()
                pagina = self._coletar_pagina(url)
                if pagina is None:
                    break
                coletados.extend(self.converter_pagina(pagina))
                if not pagina.tem_proxima:
                    break
                numero += 1

        return coletados

    # --- passos que cada loja define ou ajusta -----------------------------

    @abstractmethod
    def extrair_pagina(self, html: str) -> PaginaDeListagem:
        """Lê uma página de categoria. Deve lançar PaginaInvalida se não conseguir."""

    def url_da_pagina(self, url_listagem: str, numero: int) -> Optional[str]:
        """URL da página `numero` (a partir de 1), ou None se a loja não deixa abri-la."""
        return url_listagem if numero <= 1 else None

    def converter_pagina(self, pagina: PaginaDeListagem) -> list[ObservacaoDeProduto]:
        return [converter(item.produto, item.url, self.loja) for item in pagina.itens]

    # --- ajudantes ---------------------------------------------------------

    def esperar_a_vez(self) -> None:
        """Espera o intervalo antes de cada requisição, menos a primeira da rodada."""
        if not self._primeira_requisicao and self._intervalo > 0:
            self._esperar(self._intervalo)
        self._primeira_requisicao = False

    def _coletar_pagina(self, url: str) -> Optional[PaginaDeListagem]:
        try:
            pagina = self.extrair_pagina(self._baixar(url))
        except (requests.RequestException, PaginaInvalida, ValueError) as erro:
            logger.warning("%s: falha ao coletar a listagem %s: %s", self.loja, url, erro)
            return None
        logger.info(
            "%s: listagem %s, página %d de %d, %d produto(s)",
            self.loja, url, pagina.pagina_atual, pagina.total_paginas, len(pagina.itens),
        )
        return pagina
