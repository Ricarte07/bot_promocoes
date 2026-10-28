"""Adaptador da porta PublicadorDeEventos que só imprime no terminal.

Serve para a versão 0.1.0 e para depuração. O Redis entra depois como outro adaptador.
"""

from typing import Callable

from application.portas import PublicadorDeEventos
from domain.eventos import PromocaoDetectada


class PublicadorNoConsole(PublicadorDeEventos):
    def __init__(self, escrever: Callable[[str], None] = print):
        self._escrever = escrever

    def publicar(self, evento: PromocaoDetectada) -> None:
        descricao = evento.nome or f"produto {evento.produto_id}"
        self._escrever(
            f"[PROMOÇÃO] {evento.loja} | {descricao} | "
            f"de R$ {evento.preco_referencia} por R$ {evento.preco_atual} "
            f"({evento.desconto_percentual}% de desconto) {evento.url}".rstrip()
        )
