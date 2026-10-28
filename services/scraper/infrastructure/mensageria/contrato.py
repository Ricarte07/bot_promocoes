"""Serializa PromocaoDetectada no formato combinado com o notifier.

O contrato está em docs/evento-promocao.md. Este módulo é a única parte do
scraper que conhece esse formato: qualquer adaptador de publicação (Redis,
arquivo, HTTP) chama serializar_evento e não monta JSON por conta própria.
"""

import json
from decimal import Decimal

from domain.eventos import PromocaoDetectada

TIPO = "promocao_detectada"
VERSAO = 1

_DUAS_CASAS = Decimal("0.01")


def _dinheiro(valor: Decimal) -> str:
    """Decimal com exatamente duas casas e ponto, como "901.55"."""
    return str(valor.quantize(_DUAS_CASAS))


def serializar_evento(evento: PromocaoDetectada) -> str:
    """Devolve o JSON do evento, com preços em texto para nunca virarem float."""
    dados = {
        "tipo": TIPO,
        "versao": VERSAO,
        "produto_id": evento.produto_id,
        "loja": evento.loja,
        "nome": evento.nome,
        "url": evento.url,
        "preco_atual": _dinheiro(evento.preco_atual),
        "preco_referencia": _dinheiro(evento.preco_referencia),
        "desconto_percentual": _dinheiro(evento.desconto_percentual),
        "ocorrido_em": evento.ocorrido_em.isoformat(),
    }
    return json.dumps(dados, ensure_ascii=False)
