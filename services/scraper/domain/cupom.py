from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Cupom:
    """Value Object: cupom que a loja anuncia na página do produto.

    desconto_percentual fica None quando a loja mostra o código mas não diz
    quanto ele desconta (caso da Americanas). Nesse caso o cupom vai na
    mensagem, mas não entra na conta do preço final.
    """

    codigo: str
    desconto_percentual: Optional[Decimal] = None

    def __post_init__(self):
        if not self.codigo or not self.codigo.strip():
            raise ValueError("Cupom precisa de um código")
        if self.desconto_percentual is not None:
            if not isinstance(self.desconto_percentual, Decimal):
                raise TypeError("Use Decimal para o percentual, nunca float")
            if not (0 < self.desconto_percentual < 100):
                raise ValueError("Percentual do cupom deve estar entre 0 e 100")

    def aplicar(self, valor: Decimal) -> Decimal:
        """Devolve o valor com o cupom aplicado, arredondado a centavos."""
        if self.desconto_percentual is None:
            return valor
        final = valor * (100 - self.desconto_percentual) / 100
        return final.quantize(Decimal("0.01"))
