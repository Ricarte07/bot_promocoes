"""Serializa PromocaoDetectada no formato combinado com o notifier.

O contrato está em docs/evento-promocao.md. Este módulo é a única parte do
scraper que conhece esse formato: qualquer adaptador de publicação (Redis,
arquivo, HTTP) chama serializar_evento e não monta JSON por conta própria.
"""

import json
from decimal import Decimal
from typing import Optional

from domain.cupom import Cupom
from domain.eventos import PromocaoDetectada

TIPO = "promocao_detectada"
VERSAO = 2

_DUAS_CASAS = Decimal("0.01")


def _dinheiro(valor: Decimal) -> str:
    """Decimal com exatamente duas casas e ponto, como "901.55"."""
    return str(valor.quantize(_DUAS_CASAS))


def _cupom(cupom: Optional[Cupom]) -> Optional[dict]:
    if cupom is None:
        return None
    return {
        "codigo": cupom.codigo,
        "desconto_percentual": (
            _dinheiro(cupom.desconto_percentual) if cupom.desconto_percentual is not None else None
        ),
    }


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
        "preco_final": _dinheiro(evento.preco_final),
        "preco_referencia": _dinheiro(evento.preco_referencia),
        "desconto_percentual": _dinheiro(evento.desconto_percentual),
        "cupom": _cupom(evento.cupom),
        "ocorrido_em": evento.ocorrido_em.isoformat(),
    }
    return json.dumps(dados, ensure_ascii=False)
