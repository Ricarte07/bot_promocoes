from decimal import Decimal

from application.portas import ColetorDePrecos, PrecoColetado, PublicadorDeEventos
from application.processar_coleta import ProcessarColeta
from domain.cupom import Cupom
from domain.preco import Preco
from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria


class ColetorFalso(ColetorDePrecos):
    def __init__(self):
        self.precos = []

    def coletar(self):
        return self.precos


class PublicadorFalso(PublicadorDeEventos):
    def __init__(self):
        self.publicados = []

    def publicar(self, evento):
        self.publicados.append(evento)


def montar():
    coletor = ColetorFalso()
    publicador = PublicadorFalso()
    caso_de_uso = ProcessarColeta(coletor, OfertaRepositorioEmMemoria(), publicador)
    return coletor, publicador, caso_de_uso


def item(valor, cupom=None):
    return PrecoColetado(
        "notebook-x",
        "loja-a",
        Preco(Decimal(valor)),
        nome="Notebook X",
        url="https://loja-a.com/notebook-x",
        cupom=cupom,
    )


def test_primeira_coleta_so_registra_a_oferta():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [item("1000")]
    assert caso_de_uso.executar() == 0
    assert publicador.publicados == []


def test_queda_grande_publica_promocao():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [item("1000")]
    caso_de_uso.executar()
    coletor.precos = [item("800")]
    assert caso_de_uso.executar() == 1
    evento = publicador.publicados[0]
    assert evento.desconto_percentual == Decimal("20.00")
    assert evento.nome == "Notebook X"
    assert evento.url == "https://loja-a.com/notebook-x"


def test_queda_pequena_nao_publica():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [item("1000")]
    caso_de_uso.executar()
    coletor.precos = [item("950")]
    assert caso_de_uso.executar() == 0
    assert publicador.publicados == []


def test_cupom_coletado_chega_ao_evento():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [item("1000")]
    caso_de_uso.executar()
    coletor.precos = [item("1000", Cupom("QUINZE", Decimal("15")))]

    assert caso_de_uso.executar() == 1
    evento = publicador.publicados[0]
    assert evento.cupom == Cupom("QUINZE", Decimal("15"))
    assert evento.preco_final == Decimal("850.00")
