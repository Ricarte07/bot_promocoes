"""Adaptador da porta PublicadorDeEventos que escreve num Redis Stream.

Cada promoção vira uma entrada no stream `promocoes` com um único campo,
`json`, no formato de docs/evento-promocao.md. O notifier em Go lê desse
mesmo stream com um consumer group, então a mensagem fica guardada até ele
confirmar que a processou.

O cliente Redis entra pelo construtor: em produção é redis.from_url(...),
nos testes é um objeto falso que só grava o que recebeu.
"""

import logging
from typing import Any, Protocol

from application.portas import PublicadorDeEventos
from domain.eventos import PromocaoDetectada
from infrastructure.mensageria.contrato import serializar_evento

STREAM_PADRAO = "promocoes"
CAMPO_JSON = "json"
TAMANHO_MAXIMO_PADRAO = 1000  # entradas mantidas no stream; as mais antigas são descartadas

logger = logging.getLogger(__name__)


class ClienteRedis(Protocol):
    """O único método do redis-py que usamos. Facilita o teste sem servidor."""

    def xadd(
        self, name: str, fields: dict[str, Any], maxlen: int | None = ..., approximate: bool = ...
    ) -> Any: ...


class PublicadorRedis(PublicadorDeEventos):
    def __init__(
        self,
        cliente: ClienteRedis,
        stream: str = STREAM_PADRAO,
        tamanho_maximo: int = TAMANHO_MAXIMO_PADRAO,
    ):
        self._cliente = cliente
        self._stream = stream
        self._tamanho_maximo = tamanho_maximo

    def publicar(self, evento: PromocaoDetectada) -> None:
        entrada_id = self._cliente.xadd(
            self._stream,
            {CAMPO_JSON: serializar_evento(evento)},
            maxlen=self._tamanho_maximo,
            approximate=True,  # o Redis apara em blocos, o que é mais barato que o corte exato
        )
        logger.info(
            "Redis: promoção de %s/%s publicada no stream %s (id %s)",
            evento.loja,
            evento.produto_id,
            self._stream,
            entrada_id,
        )
