from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from domain.cupom import Cupom
from domain.eventos import PromocaoDetectada
from domain.preco import Preco


@dataclass(frozen=True)
class PrecoColetado:
    """Um preço visto numa loja, com o que a notificação precisa: nome e link do produto."""

    produto_id: str
    loja: str
    preco: Preco
    nome: str = ""
    url: str = ""
    cupom: Optional[Cupom] = None  # cupom anunciado na página, se houver
    preco_de: Optional[Preco] = None  # preço "de" que a loja anuncia, se houver


@dataclass(frozen=True)
class ProdutoMonitorado:
    """Um endereço a visitar: em qual loja e em qual URL está o produto."""

    loja: str
    url: str


class ColetorDePrecos(ABC):
    """Porta de entrada: cada loja terá um adaptador em infrastructure/scrapers."""

    @abstractmethod
    def coletar(self) -> list[PrecoColetado]: ...


class FonteDeProdutosMonitorados(ABC):
    """Porta de saída: de onde vem a lista do que monitorar (JSON hoje, banco depois)."""

    @abstractmethod
    def listar(self) -> list[ProdutoMonitorado]: ...


class PublicadorDeEventos(ABC):
    """Porta de saída: depois será implementada com Redis."""

    @abstractmethod
    def publicar(self, evento: PromocaoDetectada) -> None: ...
