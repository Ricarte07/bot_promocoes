from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Preco:
    """Value Object: imutável e comparado pelo valor."""

    valor: Decimal

    def __post_init__(self):
        if not isinstance(self.valor, Decimal):
            raise TypeError("Use Decimal para dinheiro, nunca float")
        if self.valor <= 0:
            raise ValueError("Preço deve ser maior que zero")

    @classmethod
    def de_texto(cls, texto: str) -> "Preco":
        """Converte textos como 'R$ 1.299,90' em Preco."""
        limpo = texto.replace("R$", "").strip().replace(".", "").replace(",", ".")
        return cls(Decimal(limpo))

    def desconto_percentual(self, referencia: "Preco") -> Decimal:
        if self.valor >= referencia.valor:
            return Decimal("0")
        desconto = (referencia.valor - self.valor) / referencia.valor * 100
        return desconto.quantize(Decimal("0.01"))
