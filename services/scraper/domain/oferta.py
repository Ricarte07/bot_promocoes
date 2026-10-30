from decimal import Decimal
from typing import Optional

from domain.cupom import Cupom
from domain.eventos import PromocaoDetectada
from domain.preco import Preco


class Oferta:
    """Aggregate Root: único ponto de entrada para mudar o preço de um produto numa loja.

    Guarda dois preços: o da página (preco_atual) e o que o comprador paga de
    fato (preco_final), já com o cupom aplicado quando a loja diz quanto ele
    desconta. A regra dos 15% olha para o preco_final.
    """

    DESCONTO_MINIMO = Decimal("15")

    def __init__(
        self,
        produto_id: str,
        loja: str,
        preco_referencia: Preco,
        nome: str = "",
        url: str = "",
        cupom: Optional[Cupom] = None,
    ):
        self.produto_id = produto_id
        self.loja = loja
        self.nome = nome
        self.url = url
        self.preco_referencia = preco_referencia  # preço da página na primeira coleta
        self.preco_atual = preco_referencia
        self.cupom = cupom
        self.preco_final = self._com_cupom(preco_referencia, cupom)
        self._eventos: list[PromocaoDetectada] = []

    def registrar_preco(self, novo_preco: Preco, cupom: Optional[Cupom] = None) -> None:
        final_anterior = self.preco_final

        self.preco_atual = novo_preco
        self.cupom = cupom
        self.preco_final = self._com_cupom(novo_preco, cupom)

        caiu = self.preco_final.valor < final_anterior.valor
        desconto = self.preco_final.desconto_percentual(self.preco_referencia)

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
                    cupom=cupom,
                )
            )

    def coletar_eventos(self) -> list[PromocaoDetectada]:
        eventos, self._eventos = self._eventos, []
        return eventos

    @staticmethod
    def _com_cupom(preco: Preco, cupom: Optional[Cupom]) -> Preco:
        if cupom is None:
            return preco
        return Preco(cupom.aplicar(preco.valor))
