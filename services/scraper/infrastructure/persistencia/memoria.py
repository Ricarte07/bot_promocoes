from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from domain.oferta import Oferta
from domain.preco import Preco
from domain.regras_promocao import HistoricoRecente
from domain.repositorios import OfertaRepositorio

JANELA = timedelta(days=30)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class OfertaRepositorioEmMemoria(OfertaRepositorio):
    """Guarda ofertas e histórico só enquanto o processo vive."""

    def __init__(self, agora: Callable[[], datetime] = _agora):
        self._ofertas: dict[tuple[str, str], Oferta] = {}
        self._historico: dict[tuple[str, str], list[tuple[datetime, Preco]]] = {}
        self._agora = agora

    def buscar(self, produto_id: str, loja: str) -> Optional[Oferta]:
        return self._ofertas.get((produto_id, loja))

    def salvar(self, oferta: Oferta) -> None:
        chave = (oferta.produto_id, oferta.loja)
        self._ofertas[chave] = oferta
        self._historico.setdefault(chave, []).append((self._agora(), oferta.preco_final))

    def historico_recente(self, produto_id: str, loja: str) -> HistoricoRecente:
        observacoes = self._historico.get((produto_id, loja), [])
        if not observacoes:
            return HistoricoRecente()
        agora = self._agora()
        recentes = [preco for quando, preco in observacoes if quando >= agora - JANELA]
        primeira = min(quando for quando, _ in observacoes)
        return HistoricoRecente(
            menor_preco_30_dias=min(recentes, key=lambda preco: preco.valor) if recentes else None,
            dias_acompanhado=(agora - primeira).total_seconds() / 86400,
        )
