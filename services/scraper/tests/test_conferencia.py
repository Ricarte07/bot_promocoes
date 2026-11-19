from decimal import Decimal

from application.conferencia import ReaproveitarSeNaoMudou
from application.portas import PrecoColetado
from domain.cupom import Cupom
from domain.oferta import Oferta
from domain.preco import Preco
from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria

DEZ = Cupom("DEZ", Decimal("10.00"))
DEZ_SEM_PERCENTUAL = Cupom("DEZ", None)  # como a listagem da Kabum mostra o cupom


def preco(valor: str) -> Preco:
    return Preco(Decimal(valor))


def reaproveitar_com(valor: str, preco_de=None, cupom=None) -> ReaproveitarSeNaoMudou:
    repositorio = OfertaRepositorioEmMemoria()
    oferta = Oferta("1", "kabum", preco(valor))
    oferta.registrar_preco(preco(valor), cupom=cupom, preco_de=preco_de)
    repositorio.salvar(oferta)
    return ReaproveitarSeNaoMudou(repositorio)


def visto(valor: str, preco_de=None, cupom=None) -> PrecoColetado:
    return PrecoColetado("1", "kabum", preco(valor), "Nome", "https://loja/1", cupom, preco_de)


def test_produto_novo_precisa_ser_conferido():
    assert ReaproveitarSeNaoMudou(OfertaRepositorioEmMemoria())(visto("100")) is None


def test_produto_igual_ao_ultimo_registro_e_reaproveitado():
    reaproveitar = reaproveitar_com("100", preco_de=preco("150"))
    # 100 e 100.00 são o mesmo valor: o banco devolve com 2 casas.
    assert reaproveitar(visto("100.00", preco_de=preco("150"))) == visto("100.00", preco_de=preco("150"))


def test_cupom_sem_percentual_na_listagem_reaproveita_o_percentual_confirmado():
    reaproveitar = reaproveitar_com("100", cupom=DEZ)

    reaproveitado = reaproveitar(visto("100", cupom=DEZ_SEM_PERCENTUAL))

    assert reaproveitado.cupom == DEZ  # sem isso o preço final perderia o desconto do cupom


def test_qualquer_mudanca_precisa_ser_conferida():
    reaproveitar = reaproveitar_com("100", preco_de=preco("150"), cupom=DEZ)

    assert reaproveitar(visto("99.99", preco_de=preco("150"), cupom=DEZ)) is None
    assert reaproveitar(visto("100", preco_de=preco("160"), cupom=DEZ)) is None
    assert reaproveitar(visto("100", preco_de=None, cupom=DEZ)) is None
    assert reaproveitar(visto("100", preco_de=preco("150"), cupom=Cupom("OUTRO", None))) is None
    assert reaproveitar(visto("100", preco_de=preco("150"), cupom=Cupom("DEZ", Decimal("15")))) is None
    assert reaproveitar(visto("100", preco_de=preco("150"), cupom=None)) is None


def test_cupom_novo_precisa_ser_conferido():
    assert reaproveitar_com("100")(visto("100", cupom=DEZ_SEM_PERCENTUAL)) is None
