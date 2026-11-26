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
    # Slug da categoria (tabela categorias), herdado da listagem ou do item avulso
    # do produtos.json onde o produto foi visto. None quando não foi informada.
    categoria: Optional[str] = None


@dataclass(frozen=True)
class ProdutoSemEstoque:
    """A loja confirmou que o produto está indisponível: a oferta guardada sai."""

    produto_id: str
    loja: str


ObservacaoDeProduto = PrecoColetado | ProdutoSemEstoque


TIPO_PRODUTO = "produto"
TIPO_LISTAGEM = "listagem"


@dataclass(frozen=True)
class ProdutoMonitorado:
    """Um endereço a visitar numa loja.

    tipo "produto": a URL é a página de um único produto.
    tipo "listagem": a URL é uma página de categoria ou de ofertas, e todos os
    produtos dela entram no monitoramento. paginas diz quantas páginas da
    listagem seguir (só vale para listagens). categoria é o slug da tabela
    categorias que todo produto visto neste endereço recebe.
    """

    loja: str
    url: str
    tipo: str = TIPO_PRODUTO
    paginas: int = 1
    categoria: Optional[str] = None


class BancoDesatualizado(RuntimeError):
    """Falta uma migração de sql/ no banco. A mensagem diz qual e não traz credenciais."""


class ColetorDePrecos(ABC):
    """Porta de entrada: cada loja terá um adaptador em infrastructure/scrapers."""

    @abstractmethod
    def coletar(self) -> list[ObservacaoDeProduto]: ...


class FonteDeProdutosMonitorados(ABC):
    """Porta de saída: de onde vem a lista do que monitorar (JSON hoje, banco depois)."""

    @abstractmethod
    def listar(self) -> list[ProdutoMonitorado]: ...


class PublicadorDeEventos(ABC):
    """Porta de saída: depois será implementada com Redis."""

    @abstractmethod
    def publicar(self, evento: PromocaoDetectada) -> None: ...
