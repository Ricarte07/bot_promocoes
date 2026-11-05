from abc import ABC, abstractmethod
from contextlib import nullcontext
from typing import Optional

from domain.oferta import Oferta


class OfertaRepositorio(ABC):
    def transacao(self, produto_id: str, loja: str):
        return nullcontext()

    @abstractmethod
    def buscar(self, produto_id: str, loja: str) -> Optional[Oferta]: ...

    @abstractmethod
    def salvar(self, oferta: Oferta) -> None: ...
