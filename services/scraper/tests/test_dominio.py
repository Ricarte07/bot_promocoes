from decimal import Decimal

import pytest

from domain.cupom import Cupom
from domain.oferta import Oferta
from domain.preco import Preco


def nova_oferta():
    return Oferta(
        "notebook-x",
        "loja-a",
        Preco(Decimal("1000")),
        nome="Notebook X",
        url="https://loja-a.com/notebook-x",
    )


def test_preco_nao_aceita_zero():
    with pytest.raises(ValueError):
        Preco(Decimal("0"))


def test_preco_a_partir_de_texto():
    assert Preco.de_texto("R$ 1.299,90") == Preco(Decimal("1299.90"))


def test_detecta_promocao_com_desconto_suficiente():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("800")))
    eventos = oferta.coletar_eventos()
    assert len(eventos) == 1
    assert eventos[0].desconto_percentual == Decimal("20.00")
    assert eventos[0].nome == "Notebook X"
    assert eventos[0].url == "https://loja-a.com/notebook-x"


def test_ignora_desconto_pequeno():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("950")))
    assert oferta.coletar_eventos() == []


def test_nao_repete_promocao_se_preco_nao_mudou():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("800")))
    oferta.coletar_eventos()
    oferta.registrar_preco(Preco(Decimal("800")))
    assert oferta.coletar_eventos() == []


# --- cupom ------------------------------------------------------------------


def test_cupom_aplica_percentual_e_arredonda_a_centavos():
    assert Cupom("ESQUENTA", Decimal("5")).aplicar(Decimal("279.99")) == Decimal("265.99")
    assert Cupom("DEZ", Decimal("10")).aplicar(Decimal("1000")) == Decimal("900.00")


def test_cupom_sem_valor_conhecido_nao_muda_o_preco():
    assert Cupom("10DO10").aplicar(Decimal("901.55")) == Decimal("901.55")


def test_cupom_exige_codigo_e_percentual_valido():
    with pytest.raises(ValueError):
        Cupom("")
    with pytest.raises(ValueError):
        Cupom("X", Decimal("100"))
    with pytest.raises(TypeError):
        Cupom("X", 10.0)


def test_cupom_conhecido_entra_na_regra_dos_15():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), Cupom("QUINZE", Decimal("15")))

    eventos = oferta.coletar_eventos()

    assert len(eventos) == 1
    assert eventos[0].preco_atual == Decimal("1000")
    assert eventos[0].preco_final == Decimal("850.00")
    assert eventos[0].desconto_percentual == Decimal("15.00")
    assert eventos[0].cupom == Cupom("QUINZE", Decimal("15"))


def test_queda_pequena_mais_cupom_somam_os_15():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("900")), Cupom("DEZ", Decimal("10")))

    eventos = oferta.coletar_eventos()

    assert len(eventos) == 1
    assert eventos[0].preco_final == Decimal("810.00")
    assert eventos[0].desconto_percentual == Decimal("19.00")


def test_cupom_sem_valor_conhecido_nao_dispara_sozinho():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), Cupom("10DO10"))
    assert oferta.coletar_eventos() == []


def test_cupom_sem_valor_vai_junto_quando_o_preco_cai():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("800")), Cupom("10DO10"))

    eventos = oferta.coletar_eventos()

    assert len(eventos) == 1
    assert eventos[0].cupom == Cupom("10DO10")
    assert eventos[0].preco_final == Decimal("800")


def test_cupom_que_some_nao_dispara_nem_repete():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), Cupom("QUINZE", Decimal("15")))
    oferta.coletar_eventos()

    oferta.registrar_preco(Preco(Decimal("1000")))  # cupom acabou: preço final subiu
    assert oferta.coletar_eventos() == []

    oferta.registrar_preco(Preco(Decimal("1000")), Cupom("QUINZE", Decimal("15")))  # voltou
    assert len(oferta.coletar_eventos()) == 1


def test_cupom_presente_na_primeira_coleta_ja_e_promocao():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), Cupom("QUINZE", Decimal("15")))

    assert len(oferta.coletar_eventos()) == 1

    oferta.registrar_preco(Preco(Decimal("1000")), Cupom("QUINZE", Decimal("15")))
    assert oferta.coletar_eventos() == []  # nada mudou, não repete


# --- desconto anunciado pela loja (preço "de") ---------------------------------


def test_desconto_anunciado_na_primeira_coleta_ja_e_promocao():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("1250")))

    eventos = oferta.coletar_eventos()

    assert len(eventos) == 1
    assert eventos[0].preco_atual == Decimal("1000")
    assert eventos[0].preco_referencia == Decimal("1250")  # a base foi o "de" da loja
    assert eventos[0].desconto_percentual == Decimal("20.00")


def test_desconto_anunciado_nao_repete_enquanto_nada_muda():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("1250")))
    oferta.coletar_eventos()

    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("1250")))
    assert oferta.coletar_eventos() == []


def test_desconto_anunciado_pequeno_nao_dispara():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("1100")))
    assert oferta.coletar_eventos() == []


def test_preco_de_menor_que_o_por_e_ignorado():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("900")))
    assert oferta.coletar_eventos() == []


def test_cupom_e_desconto_anunciado_se_somam():
    oferta = nova_oferta()
    oferta.registrar_preco(
        Preco(Decimal("1000")), Cupom("DEZ", Decimal("10")), preco_de=Preco(Decimal("1100"))
    )

    eventos = oferta.coletar_eventos()

    assert len(eventos) == 1
    assert eventos[0].preco_final == Decimal("900.00")
    assert eventos[0].desconto_percentual == Decimal("18.18")


def test_promocao_que_acaba_e_volta_dispara_de_novo():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("1250")))
    oferta.coletar_eventos()

    oferta.registrar_preco(Preco(Decimal("1000")))  # loja tirou o "de"
    assert oferta.coletar_eventos() == []

    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("1250")))
    assert len(oferta.coletar_eventos()) == 1


def test_queda_adicional_durante_a_promocao_dispara_de_novo():
    oferta = nova_oferta()
    oferta.registrar_preco(Preco(Decimal("1000")), preco_de=Preco(Decimal("1250")))
    oferta.coletar_eventos()

    oferta.registrar_preco(Preco(Decimal("900")), preco_de=Preco(Decimal("1250")))

    eventos = oferta.coletar_eventos()
    assert len(eventos) == 1
    assert eventos[0].desconto_percentual == Decimal("28.00")
