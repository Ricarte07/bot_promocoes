from decimal import Decimal

import pytest

from domain.oferta import Oferta
from domain.preco import Preco


def nova_oferta():
    return Oferta("notebook-x", "loja-a", Preco(Decimal("1000")))


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
