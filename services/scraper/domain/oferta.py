from typing import Optional

from domain.cupom import Cupom
from domain.eventos import PromocaoDetectada
from domain.preco import Preco
from domain.regras_promocao import (
    TIPO_PRECO_DE,
    TIPO_REFERENCIA,
    Candidato,
    Contexto,
    HistoricoRecente,
    Regra,
    cadeia_padrao,
)


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

    Se é promoção, quem decide é a cadeia de regras (domain/regras_promocao.py):
    desconto mínimo de 15% e, para o preço "de", a conferência com o menor
    preço dos últimos 30 dias. O evento sai quando a oferta entra em promoção
    ou quando, já em promoção, o preço final cai mais um pouco. Enquanto nada
    muda, não se repete.
    """

    REGRAS: Regra = cadeia_padrao()

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
        historico: Optional[HistoricoRecente] = None,
    ) -> None:
        """historico: o que o bot já viu antes desta coleta. Sem ele, o produto
        é tratado como recém-descoberto (o "de" da loja não pode ser conferido)."""
        final_anterior = self.preco_final
        estava_em_promocao = self.em_promocao

        self.preco_atual = novo_preco
        self.cupom = cupom
        self.preco_de = preco_de
        self.preco_final = self._com_cupom(novo_preco, cupom)

        promocao = self._melhor_promocao(historico or HistoricoRecente())
        self.em_promocao = promocao is not None
        caiu = self.preco_final.valor < final_anterior.valor

        if promocao is not None and (not estava_em_promocao or caiu):
            self._eventos.append(
                PromocaoDetectada(
                    produto_id=self.produto_id,
                    loja=self.loja,
                    preco_atual=novo_preco.valor,
                    preco_referencia=promocao.base.valor,
                    desconto_percentual=promocao.desconto,
                    nome=self.nome,
                    url=self.url,
                    cupom=cupom,
                    base_desconto=promocao.origem or "",
                )
            )

    def coletar_eventos(self) -> list[PromocaoDetectada]:
        eventos, self._eventos = self._eventos, []
        return eventos

    def _melhor_promocao(self, historico: HistoricoRecente) -> Optional[Candidato]:
        """Passa cada base pela cadeia de regras e fica com o maior desconto aprovado.

        Em empate fica a referência, que vem primeiro: é a base mais confiável,
        porque o preço "de" é a loja quem diz, e às vezes ele vem inflado.
        """
        candidatos = [Candidato(self.preco_referencia, TIPO_REFERENCIA,
                                self.preco_final.desconto_percentual(self.preco_referencia))]
        if self.preco_de is not None:
            candidatos.append(Candidato(self.preco_de, TIPO_PRECO_DE,
                                        self.preco_final.desconto_percentual(self.preco_de)))

        contexto = Contexto(self.preco_final, historico)
        aprovados = [c for c in (self.REGRAS.avaliar(c, contexto) for c in candidatos) if c]
        return max(aprovados, key=lambda c: c.desconto, default=None)

    @staticmethod
    def _com_cupom(preco: Preco, cupom: Optional[Cupom]) -> Preco:
        if cupom is None:
            return preco
        return Preco(cupom.aplicar(preco.valor))
