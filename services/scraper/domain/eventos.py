from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from domain.cupom import Cupom


@dataclass(frozen=True)
class PromocaoDetectada:
    produto_id: str
    loja: str
    preco_atual: Decimal  # preço mostrado na página, sem cupom
    preco_referencia: Decimal
    desconto_percentual: Decimal  # calculado sobre o preco_final
    nome: str = ""
    url: str = ""
    cupom: Optional[Cupom] = None
    # De onde vem o desconto: "referencia", "menor_30_dias" ou "preco_de_loja"
    # (ver domain/regras_promocao.py). Vazio em eventos montados fora da Oferta.
    base_desconto: str = ""
    # Slug da categoria do produto (tabela categorias); None quando não se sabe.
    categoria: Optional[str] = None
    ocorrido_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def preco_final(self) -> Decimal:
        """O que o comprador paga: preco_atual com o cupom aplicado, se houver."""
        if self.cupom is None:
            return self.preco_atual
        return self.cupom.aplicar(self.preco_atual)
