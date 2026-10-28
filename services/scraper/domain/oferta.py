from decimal import Decimal

from domain.eventos import PromocaoDetectada
from domain.preco import Preco


class Oferta:
    """Aggregate Root: único ponto de entrada para mudar o preço de um produto numa loja."""

    DESCONTO_MINIMO = Decimal("15")

    def __init__(
        self,
        produto_id: str,
        loja: str,
        preco_referencia: Preco,
        nome: str = "",
        url: str = "",
    ):
        self.produto_id = produto_id
        self.loja = loja
        self.nome = nome
        self.url = url
        self.preco_referencia = preco_referencia
        self.preco_atual = preco_referencia
        self._eventos: list[PromocaoDetectada] = []

    def registrar_preco(self, novo_preco: Preco) -> None:
        preco_anterior = self.preco_atual
        self.preco_atual = novo_preco

        caiu = novo_preco.valor < preco_anterior.valor
        desconto = novo_preco.desconto_percentual(self.preco_referencia)

        if caiu and desconto >= self.DESCONTO_MINIMO:
            self._eventos.append(
                PromocaoDetectada(
                    produto_id=self.produto_id,
                    loja=self.loja,
                    preco_atual=novo_preco.valor,
                    preco_referencia=self.preco_referencia.valor,
                    desconto_percentual=desconto,
                    nome=self.nome,
                    url=self.url,
                )
            )

    def coletar_eventos(self) -> list[PromocaoDetectada]:
        eventos, self._eventos = self._eventos, []
        return eventos
