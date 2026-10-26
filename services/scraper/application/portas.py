from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.eventos import PromocaoDetectada
from domain.preco import Preco


@dataclass(frozen=True)
class PrecoColetado:
    produto_id: str
    loja: str
    preco: Preco


class ColetorDePrecos(ABC):
    """Porta de entrada: cada loja terá um adaptador em infrastructure/scrapers."""

    @abstractmethod
    def coletar(self) -> list[PrecoColetado]: ...


class PublicadorDeEventos(ABC):
    """Porta de saída: depois será implementada com Redis."""

    @abstractmethod
    def publicar(self, evento: PromocaoDetectada) -> None: ...
