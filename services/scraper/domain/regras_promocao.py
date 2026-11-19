"""Regras que decidem se um desconto é promoção, encadeadas (Chain of Responsibility).

Cada base de desconto possível vira um Candidato: a referência (primeiro preço
que o bot viu) e o preço "de" anunciado pela loja. O candidato passa pela
cadeia; cada regra pode recusá-lo (devolve None) ou deixá-lo seguir, às vezes
anotando de onde vem o desconto. Os que chegam ao fim são promoções válidas, e
a Oferta escolhe a de maior desconto.

Para mudar a política (outra regra, outra ordem), mexe-se só na cadeia montada
em cadeia_padrao(), sem tocar na Oferta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Optional

from domain.preco import Preco

# Origem do desconto, como vai no evento (campo base_desconto do contrato v3).
REFERENCIA = "referencia"  # o próprio bot viu o preço cair
MENOR_30_DIAS = "menor_30_dias"  # "de" da loja confirmado pelo histórico do bot
PRECO_DE_LOJA = "preco_de_loja"  # "de" da loja, sem histórico suficiente para conferir

TIPO_REFERENCIA = "referencia"
TIPO_PRECO_DE = "preco_de"


@dataclass(frozen=True)
class HistoricoRecente:
    """O que o bot já sabe do produto antes desta coleta.

    menor_preco_30_dias: menor preço final visto nos últimos 30 dias (None se não há).
    dias_acompanhado: há quantos dias o bot viu o produto pela primeira vez.
    """

    menor_preco_30_dias: Optional[Preco] = None
    dias_acompanhado: float = 0.0


@dataclass(frozen=True)
class Candidato:
    base: Preco
    tipo: str  # TIPO_REFERENCIA ou TIPO_PRECO_DE
    desconto: Decimal
    origem: Optional[str] = None


@dataclass(frozen=True)
class Contexto:
    preco_final: Preco
    historico: HistoricoRecente


class Regra(ABC):
    """Um elo da cadeia. avaliar() aplica esta regra e repassa para a próxima."""

    def __init__(self, proxima: Optional["Regra"] = None):
        self.proxima = proxima

    def avaliar(self, candidato: Candidato, contexto: Contexto) -> Optional[Candidato]:
        resultado = self.aplicar(candidato, contexto)
        if resultado is None or self.proxima is None:
            return resultado
        return self.proxima.avaliar(resultado, contexto)

    @abstractmethod
    def aplicar(self, candidato: Candidato, contexto: Contexto) -> Optional[Candidato]:
        """Devolve o candidato (talvez anotado) para seguir, ou None para recusar."""


class DescontoMinimo(Regra):
    """Abaixo do mínimo não é promoção, venha o desconto de onde vier."""

    def __init__(self, minimo: Decimal, proxima: Optional[Regra] = None):
        super().__init__(proxima)
        self.minimo = minimo

    def aplicar(self, candidato, contexto):
        return candidato if candidato.desconto >= self.minimo else None


class QuedaVistaPeloBot(Regra):
    """Desconto sobre a referência é queda que o próprio bot acompanhou: confiável."""

    def aplicar(self, candidato, contexto):
        if candidato.tipo != TIPO_REFERENCIA:
            return candidato
        return replace(candidato, origem=REFERENCIA)


class PrecoDeConferidoPeloHistorico(Regra):
    """O "de" da loja só vale se o preço também for o menor dos últimos 30 dias.

    Pega o truque de subir o preço antes de anunciar o "desconto" (comum perto
    da Black Friday). Com pouco histórico não há como conferir: o candidato
    segue, marcado como "informado pela loja", para a mensagem avisar.
    """

    def __init__(self, dias_minimos: float, proxima: Optional[Regra] = None):
        super().__init__(proxima)
        self.dias_minimos = dias_minimos

    def aplicar(self, candidato, contexto):
        if candidato.tipo != TIPO_PRECO_DE:
            return candidato
        historico = contexto.historico
        if historico.dias_acompanhado < self.dias_minimos or historico.menor_preco_30_dias is None:
            return replace(candidato, origem=PRECO_DE_LOJA)
        if contexto.preco_final.valor <= historico.menor_preco_30_dias.valor:
            return replace(candidato, origem=MENOR_30_DIAS)
        return None  # "de" inflado: o bot já viu preço menor nos últimos 30 dias


DESCONTO_MINIMO = Decimal("15")
DIAS_PARA_CONFERIR = 7


def cadeia_padrao() -> Regra:
    return DescontoMinimo(
        DESCONTO_MINIMO,
        proxima=QuedaVistaPeloBot(proxima=PrecoDeConferidoPeloHistorico(DIAS_PARA_CONFERIR)),
    )
