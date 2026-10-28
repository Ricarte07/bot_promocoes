from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class PromocaoDetectada:
    produto_id: str
    loja: str
    preco_atual: Decimal
    preco_referencia: Decimal
    desconto_percentual: Decimal
    nome: str = ""
    url: str = ""
    ocorrido_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
