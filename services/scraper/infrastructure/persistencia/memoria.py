from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from domain.oferta import Oferta
from domain.preco import Preco
from domain.regras_promocao import HistoricoRecente
from domain.repositorios import OfertaRepositorio

JANELA = timedelta(days=30)

# O que, mudando, gera uma linha nova no histórico (igual ao repositório Postgres).
Valores = tuple


def _valores(oferta: Oferta) -> Valores:
    return (oferta.preco_atual, oferta.preco_de, oferta.preco_final, oferta.cupom)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class OfertaRepositorioEmMemoria(OfertaRepositorio):
    """Guarda ofertas e histórico só enquanto o processo vive."""

    def __init__(self, agora: Callable[[], datetime] = _agora):
        self._ofertas: dict[tuple[str, str], Oferta] = {}
        self._precos_referencia: dict[tuple[str, str], Preco] = {}
        self._historico: dict[tuple[str, str], list[tuple[datetime, Valores, Preco]]] = {}
        self._agora = agora

    def buscar(self, produto_id: str, loja: str) -> Optional[Oferta]:
        return self._ofertas.get((produto_id, loja))

    def buscar_preco_referencia(self, produto_id: str, loja: str) -> Optional[Preco]:
        return self._precos_referencia.get((produto_id, loja))

    def salvar(self, oferta: Oferta) -> None:
        chave = (oferta.produto_id, oferta.loja)
        self._precos_referencia.setdefault(chave, oferta.preco_referencia)
        self._ofertas[chave] = oferta
        # Só mudanças entram no histórico, como no Postgres.
        historico = self._historico.setdefault(chave, [])
        valores = _valores(oferta)
        if not historico or historico[-1][1] != valores:
            historico.append((self._agora(), valores, oferta.preco_final))

    def remover(self, produto_id: str, loja: str) -> None:
        self._ofertas.pop((produto_id, loja), None)

    def historico_recente(self, produto_id: str, loja: str) -> HistoricoRecente:
        observacoes = self._historico.get((produto_id, loja), [])
        if not observacoes:
            return HistoricoRecente()
        agora = self._agora()
        inicio = agora - JANELA
        recentes = [preco for quando, _, preco in observacoes if quando >= inicio]
        # O preço que valia no começo da janela é o da última mudança anterior a ela.
        anteriores = [preco for quando, _, preco in observacoes if quando < inicio]
        if anteriores:
            recentes.append(anteriores[-1])
        primeira = observacoes[0][0]
        return HistoricoRecente(
            menor_preco_30_dias=min(recentes, key=lambda preco: preco.valor) if recentes else None,
            dias_acompanhado=(agora - primeira).total_seconds() / 86400,
        )
