from abc import ABC, abstractmethod
from contextlib import nullcontext
from typing import Optional

from domain.oferta import Oferta
from domain.preco import Preco
from domain.regras_promocao import HistoricoRecente


class OfertaRepositorio(ABC):
    def transacao(self, produto_id: str, loja: str):
        return nullcontext()

    @abstractmethod
    def buscar(self, produto_id: str, loja: str) -> Optional[Oferta]: ...

    @abstractmethod
    def salvar(self, oferta: Oferta) -> None: ...

    def historico_recente(self, produto_id: str, loja: str) -> HistoricoRecente:
        """Menor preço final dos últimos 30 dias e há quantos dias o produto é
        acompanhado, sem contar a coleta que está sendo processada.

        Repositório que não guarda histórico responde "nada conhecido": o preço
        "de" da loja segue sem conferência, marcado como informado pela loja.
        """
        return HistoricoRecente()

    def buscar_preco_referencia(self, produto_id: str, loja: str) -> Optional[Preco]:
        """Preço de referência guardado, mesmo depois que a oferta saiu de promoção."""
        return None

    def remover(self, produto_id: str, loja: str) -> None:
        """Tira a oferta guardada. Repositório sem persistência não tem o que tirar."""
