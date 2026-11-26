from application.portas import ColetorDePrecos, ProdutoSemEstoque, PublicadorDeEventos
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
            with self.repositorio.transacao(item.produto_id, item.loja):
                if isinstance(item, ProdutoSemEstoque):
                    self.repositorio.remover(item.produto_id, item.loja)
                    continue

                oferta = self.repositorio.buscar(item.produto_id, item.loja)

                if oferta is None:
                    # Oferta que já saiu de promoção guarda o preço de referência; reaproveitá-lo.
                    referencia = self.repositorio.buscar_preco_referencia(item.produto_id, item.loja)
                    oferta = Oferta(
                        item.produto_id,
                        item.loja,
                        preco_referencia=referencia or item.preco,
                        nome=item.nome,
                        url=item.url,
                        categoria=item.categoria,
                    )
                oferta.nome = item.nome or oferta.nome
                oferta.url = item.url or oferta.url
                # Produto que aparece em duas listagens fica com a categoria da última coleta.
                oferta.categoria = item.categoria or oferta.categoria
                # Lido antes de salvar: o histórico não inclui esta coleta.
                historico = self.repositorio.historico_recente(item.produto_id, item.loja)
                oferta.registrar_preco(
                    item.preco, cupom=item.cupom, preco_de=item.preco_de, historico=historico
                )

                self.repositorio.salvar(oferta)

                for evento in oferta.coletar_eventos():
                    self.publicador.publicar(evento)
                    publicadas += 1

        return publicadas
