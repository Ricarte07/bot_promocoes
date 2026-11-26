from dataclasses import dataclass
from decimal import Decimal
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


@dataclass(frozen=True)
class EstadoOferta:
    """Memento: a foto do que a oferta precisa para continuar de onde parou.

    Quem guarda a oferta (o repositório) grava e lê esta foto, sem conhecer os
    atributos da Oferta nem mexer neles por fora. Eventos não entram: são o que
    aconteceu numa coleta, não estado.
    """

    produto_id: str
    loja: str
    preco_referencia: Preco
    preco_atual: Preco
    preco_final: Preco
    preco_de: Optional[Preco] = None
    cupom: Optional[Cupom] = None
    em_promocao: bool = False
    nome: str = ""
    url: str = ""
    # A promoção aprovada pelas regras: de onde vem o desconto e quanto ele é.
    # None quando a oferta não está em promoção.
    base_desconto: Optional[str] = None
    desconto_percentual: Optional[Decimal] = None
    # Slug da categoria em que o produto foi visto por último (tabela categorias).
    categoria: Optional[str] = None


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
        categoria: Optional[str] = None,
    ):
        self.produto_id = produto_id
        self.loja = loja
        self.nome = nome
        self.url = url
        self.categoria = categoria
        self.preco_referencia = preco_referencia
        self.preco_atual = preco_referencia
        self.preco_de: Optional[Preco] = None
        self.cupom: Optional[Cupom] = None
        self.preco_final = preco_referencia
        self.em_promocao = False
        # Por que é promoção (referencia, menor_30_dias ou preco_de_loja) e o
        # desconto sobre a base aprovada; None fora de promoção.
        self.base_desconto: Optional[str] = None
        self.desconto_percentual: Optional[Decimal] = None
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
        self.base_desconto = promocao.origem if promocao else None
        self.desconto_percentual = promocao.desconto if promocao else None
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
                    categoria=self.categoria,
                )
            )

    def estado(self) -> EstadoOferta:
        """A foto do estado atual, para o repositório gravar."""
        return EstadoOferta(
            produto_id=self.produto_id,
            loja=self.loja,
            preco_referencia=self.preco_referencia,
            preco_atual=self.preco_atual,
            preco_final=self.preco_final,
            preco_de=self.preco_de,
            cupom=self.cupom,
            em_promocao=self.em_promocao,
            nome=self.nome,
            url=self.url,
            base_desconto=self.base_desconto,
            desconto_percentual=self.desconto_percentual,
            categoria=self.categoria,
        )

    @classmethod
    def restaurar(cls, estado: EstadoOferta) -> "Oferta":
        """Recria a oferta a partir de uma foto gravada.

        Não passa por registrar_preco: carregar o que já foi visto não é uma
        coleta nova, então não decide promoção nem gera evento.
        """
        oferta = cls(estado.produto_id, estado.loja, estado.preco_referencia,
                     nome=estado.nome, url=estado.url, categoria=estado.categoria)
        oferta.preco_atual = estado.preco_atual
        oferta.preco_final = estado.preco_final
        oferta.preco_de = estado.preco_de
        oferta.cupom = estado.cupom
        oferta.em_promocao = estado.em_promocao
        oferta.base_desconto = estado.base_desconto
        oferta.desconto_percentual = estado.desconto_percentual
        return oferta

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
