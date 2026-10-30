from application.portas import ColetorDePrecos, PublicadorDeEventos
from domain.oferta import Oferta
from domain.repositorios import OfertaRepositorio


class ProcessarColeta:
    def __init__(
        self,
        coletor: ColetorDePrecos,
        repositorio: OfertaRepositorio,
        publicador: PublicadorDeEventos,
    ):
        self.coletor = coletor
        self.repositorio = repositorio
        self.publicador = publicador

    def executar(self) -> int:
        """Processa uma rodada de coleta e retorna quantas promoções foram publicadas."""
        publicadas = 0

        for item in self.coletor.coletar():
            oferta = self.repositorio.buscar(item.produto_id, item.loja)

            if oferta is None:
                oferta = Oferta(
                    item.produto_id,
                    item.loja,
                    preco_referencia=item.preco,
                    nome=item.nome,
                    url=item.url,
                )
            oferta.registrar_preco(item.preco, cupom=item.cupom, preco_de=item.preco_de)

            self.repositorio.salvar(oferta)

            for evento in oferta.coletar_eventos():
                self.publicador.publicar(evento)
                publicadas += 1

        return publicadas
