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


# --- Memento: EstadoOferta / Oferta.restaurar --------------------------------


def _oferta_em_promocao():
    oferta = Oferta("1", "kabum", Preco(Decimal("1000")), nome="Placa", url="https://loja/1",
                    categoria="placas-de-video")
    oferta.registrar_preco(Preco(Decimal("900")), cupom=Cupom("DEZ", Decimal("10")),
                           preco_de=Preco(Decimal("1200")))
    oferta.coletar_eventos()
    return oferta


def test_restaurar_devolve_a_mesma_foto_sem_gerar_evento():
    from domain.oferta import EstadoOferta
    original = _oferta_em_promocao()

    restaurada = Oferta.restaurar(original.estado())

    assert restaurada.estado() == original.estado()
    assert isinstance(original.estado(), EstadoOferta)
    assert restaurada.em_promocao
    assert restaurada.categoria == "placas-de-video"
    assert restaurada.preco_final.valor == Decimal("810.00")
    assert restaurada.coletar_eventos() == []


def test_oferta_restaurada_continua_de_onde_parou():
    restaurada = Oferta.restaurar(_oferta_em_promocao().estado())
    cupom = Cupom("DEZ", Decimal("10"))

    # Mesmo preço: já estava em promoção, não repete o anúncio.
    restaurada.registrar_preco(Preco(Decimal("900")), cupom=cupom, preco_de=Preco(Decimal("1200")))
    assert restaurada.coletar_eventos() == []
    # Caiu mais: anuncia de novo.
    restaurada.registrar_preco(Preco(Decimal("850")), cupom=cupom, preco_de=Preco(Decimal("1200")))
    assert len(restaurada.coletar_eventos()) == 1


def test_repositorio_em_memoria_devolve_oferta_nova_a_cada_busca():
    from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria
    repositorio = OfertaRepositorioEmMemoria()
    repositorio.salvar(_oferta_em_promocao())

    primeira = repositorio.buscar("1", "kabum")
    primeira.registrar_preco(Preco(Decimal("1")))  # mudança não salva

    assert repositorio.buscar("1", "kabum").preco_atual.valor == Decimal("900")
    assert repositorio.buscar("1", "kabum") is not repositorio.buscar("1", "kabum")


# --- Origem do desconto guardada na oferta -----------------------------------


def test_oferta_guarda_de_onde_vem_o_desconto_e_limpa_ao_sair_da_promocao():
    oferta = Oferta("1", "kabum", Preco(Decimal("1000")))
    assert (oferta.base_desconto, oferta.desconto_percentual) == (None, None)

    oferta.registrar_preco(Preco(Decimal("800")))  # queda vista pelo próprio bot
    assert oferta.base_desconto == "referencia"
    assert oferta.desconto_percentual == Decimal("20.00")

    oferta.registrar_preco(Preco(Decimal("990")))  # 1%: saiu da promoção
    assert (oferta.em_promocao, oferta.base_desconto, oferta.desconto_percentual) == (False, None, None)


def test_origem_e_desconto_entram_na_foto_da_oferta():
    oferta = Oferta("1", "kabum", Preco(Decimal("1000")))
    oferta.registrar_preco(Preco(Decimal("700")), preco_de=Preco(Decimal("1500")))

    restaurada = Oferta.restaurar(oferta.estado())

    # O "de" de 1500 dá o maior desconto (53,33%) e, sem histórico, vale como "informado pela loja".
    assert restaurada.base_desconto == "preco_de_loja"
    assert restaurada.desconto_percentual == Decimal("53.33")
    assert restaurada.estado() == oferta.estado()
