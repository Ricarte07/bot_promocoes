from typing import Optional

from domain.oferta import Oferta
from domain.repositorios import OfertaRepositorio


class OfertaRepositorioEmMemoria(OfertaRepositorio):
    def __init__(self):
        self._ofertas: dict[tuple[str, str], Oferta] = {}

    def buscar(self, produto_id: str, loja: str) -> Optional[Oferta]:
        return self._ofertas.get((produto_id, loja))

    def salvar(self, oferta: Oferta) -> None:
        self._ofertas[(oferta.produto_id, oferta.loja)] = oferta
