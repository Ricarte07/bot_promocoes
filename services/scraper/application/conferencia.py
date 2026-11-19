"""Quando um preço visto numa listagem precisa ser conferido na página do produto.

A listagem de categoria traz dezenas de produtos numa requisição, mas não traz
tudo: o cupom vem só com o código, e o quanto ele desconta só aparece na página
do produto. Conferir todos custa uma requisição (e a espera entre elas) por
produto. Basta conferir o que mudou: se a listagem mostra o mesmo que o bot já
confirmou na última coleta, a página do produto só repetiria o mesmo dado.
"""

from dataclasses import replace
from typing import Callable, Optional

from application.portas import PrecoColetado
from domain.cupom import Cupom
from domain.repositorios import OfertaRepositorio

# Recebe o que a listagem mostrou. Devolve o preço já confirmado, quando nada
# mudou, ou None quando é preciso conferir na página do produto.
JaConfirmado = Callable[[PrecoColetado], Optional[PrecoColetado]]


def nada_confirmado(_item: PrecoColetado) -> Optional[PrecoColetado]:
    return None


class ReaproveitarSeNaoMudou:
    """Reaproveita o último registro quando preço, "de" e cupom da listagem batem com ele.

    Produto novo, ou com qualquer um dos três diferente, volta None: o coletor
    confere na página.
    """

    def __init__(self, repositorio: OfertaRepositorio):
        self.repositorio = repositorio

    def __call__(self, item: PrecoColetado) -> Optional[PrecoColetado]:
        oferta = self.repositorio.buscar(item.produto_id, item.loja)
        if oferta is None:
            return None
        if oferta.preco_atual != item.preco or oferta.preco_de != item.preco_de:
            return None
        if not _mesmo_cupom(oferta.cupom, item.cupom):
            return None
        # O cupom gravado veio da página e sabe o percentual; o da listagem, não.
        return replace(item, cupom=oferta.cupom)


def _mesmo_cupom(confirmado: Optional[Cupom], visto: Optional[Cupom]) -> bool:
    if confirmado is None or visto is None:
        return confirmado == visto
    if confirmado.codigo != visto.codigo:
        return False
    # Sem percentual na listagem, vale o que a página informou da última vez.
    return visto.desconto_percentual is None or visto.desconto_percentual == confirmado.desconto_percentual
