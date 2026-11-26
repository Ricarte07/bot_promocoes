from decimal import Decimal

from application.portas import ColetorDePrecos, PrecoColetado, ProdutoSemEstoque, PublicadorDeEventos
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


def item(valor, cupom=None, preco_de=None):
    return PrecoColetado(
        "notebook-x",
        "loja-a",
        Preco(Decimal(valor)),
        nome="Notebook X",
        url="https://loja-a.com/notebook-x",
        cupom=cupom,
        preco_de=Preco(Decimal(preco_de)) if preco_de else None,
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


def test_desconto_anunciado_publica_ja_na_primeira_coleta():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [item("1000", preco_de="1300")]

    assert caso_de_uso.executar() == 1
    assert publicador.publicados[0].preco_referencia == Decimal("1300")
    assert publicador.publicados[0].desconto_percentual == Decimal("23.08")


def test_sem_estoque_remove_a_oferta_guardada():
    coletor, _, caso_de_uso = montar()
    coletor.precos = [item("1000")]
    caso_de_uso.executar()
    coletor.precos = [ProdutoSemEstoque("notebook-x", "loja-a")]
    caso_de_uso.executar()
    assert caso_de_uso.repositorio.buscar("notebook-x", "loja-a") is None


def test_oferta_que_volta_mantem_o_preco_de_referencia():
    coletor, _, caso_de_uso = montar()
    coletor.precos = [item("1000")]
    caso_de_uso.executar()
    coletor.precos = [ProdutoSemEstoque("notebook-x", "loja-a")]
    caso_de_uso.executar()
    coletor.precos = [item("900")]
    caso_de_uso.executar()
    assert caso_de_uso.repositorio.buscar("notebook-x", "loja-a").preco_referencia.valor == Decimal("1000")


# --- categoria -------------------------------------------------------------


def com_categoria(valor, categoria):
    from dataclasses import replace
    return replace(item(valor), categoria=categoria)


def test_categoria_coletada_chega_ao_evento():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [com_categoria("1000", "notebooks")]
    caso_de_uso.executar()
    coletor.precos = [com_categoria("800", "notebooks")]

    caso_de_uso.executar()

    assert publicador.publicados[0].categoria == "notebooks"


def test_produto_visto_em_outra_listagem_fica_com_a_ultima_categoria():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [com_categoria("1000", "consoles")]
    caso_de_uso.executar()
    coletor.precos = [com_categoria("800", "controles")]

    caso_de_uso.executar()

    assert publicador.publicados[0].categoria == "controles"


def test_coleta_sem_categoria_mantem_a_que_ja_se_sabia():
    coletor, publicador, caso_de_uso = montar()
    coletor.precos = [com_categoria("1000", "monitores")]
    caso_de_uso.executar()
    coletor.precos = [item("800")]

    caso_de_uso.executar()

    assert publicador.publicados[0].categoria == "monitores"
