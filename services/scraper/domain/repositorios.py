from abc import ABC, abstractmethod
from typing import Optional

from domain.oferta import Oferta


class OfertaRepositorio(ABC):
    @abstractmethod
    def buscar(self, produto_id: str, loja: str) -> Optional[Oferta]: ...

    @abstractmethod
    def salvar(self, oferta: Oferta) -> None: ...
