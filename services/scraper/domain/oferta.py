from decimal import Decimal
from typing import Optional

from domain.cupom import Cupom
from domain.eventos import PromocaoDetectada
from domain.preco import Preco


class Oferta:
    """Aggregate Root: único ponto de entrada para mudar o preço de um produto numa loja.

    Preços que a oferta acompanha:
    - preco_referencia: o primeiro preço visto na página. Serve para perceber
      quedas ao longo do tempo.
    - preco_de: o preço "de" que a loja anuncia ao lado do "por". Serve para
      perceber descontos que já estavam lá quando começamos a vigiar.
    - preco_atual: o preço "por" da página nesta coleta.
    - preco_final: o que o comprador paga, com o cupom aplicado quando a loja
      diz quanto ele desconta.

    É promoção quando o preco_final está pelo menos DESCONTO_MINIMO abaixo de
    uma das duas bases, referência ou "de". O evento sai quando a oferta entra
    em promoção ou quando, já em promoção, o preço final cai mais um pouco.
    Enquanto nada muda, não se repete.
    """

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
        self.preco_de: Optional[Preco] = None
        self.cupom: Optional[Cupom] = None
        self.preco_final = preco_referencia
        self.em_promocao = False
        self._eventos: list[PromocaoDetectada] = []

    def registrar_preco(
        self,
        novo_preco: Preco,
        cupom: Optional[Cupom] = None,
        preco_de: Optional[Preco] = None,
    ) -> None:
        final_anterior = self.preco_final
        estava_em_promocao = self.em_promocao

        self.preco_atual = novo_preco
        self.cupom = cupom
        self.preco_de = preco_de
        self.preco_final = self._com_cupom(novo_preco, cupom)

        base, desconto = self._melhor_desconto()
        self.em_promocao = desconto >= self.DESCONTO_MINIMO
        caiu = self.preco_final.valor < final_anterior.valor

        if self.em_promocao and (not estava_em_promocao or caiu):
            self._eventos.append(
                PromocaoDetectada(
                    produto_id=self.produto_id,
                    loja=self.loja,
                    preco_atual=novo_preco.valor,
                    preco_referencia=base.valor,
                    desconto_percentual=desconto,
                    nome=self.nome,
                    url=self.url,
                    cupom=cupom,
                )
            )

    def coletar_eventos(self) -> list[PromocaoDetectada]:
        eventos, self._eventos = self._eventos, []
        return eventos

    def _melhor_desconto(self) -> tuple[Preco, Decimal]:
        """Compara o preço final com cada base e devolve a que dá o maior desconto.

        Em empate fica a referência, que é a base mais confiável: o preço "de"
        é a loja quem diz, e às vezes ele vem inflado.
        """
        bases = [self.preco_referencia]
        if self.preco_de is not None:
            bases.append(self.preco_de)
        return max(
            ((base, self.preco_final.desconto_percentual(base)) for base in bases),
            key=lambda par: par[1],
        )

    @staticmethod
    def _com_cupom(preco: Preco, cupom: Optional[Cupom]) -> Preco:
        if cupom is None:
            return preco
        return Preco(cupom.aplicar(preco.valor))
