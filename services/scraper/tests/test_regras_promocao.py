"""Regras de promoção em cadeia: o "de" da loja é conferido pelo histórico do bot."""

from decimal import Decimal

from domain.oferta import Oferta
from domain.preco import Preco
from domain.regras_promocao import (
    MENOR_30_DIAS,
    PRECO_DE_LOJA,
    REFERENCIA,
    TIPO_PRECO_DE,
    Candidato,
    Contexto,
    DescontoMinimo,
    HistoricoRecente,
)


def p(valor: str) -> Preco:
    return Preco(Decimal(valor))


def acompanhado(dias: float, menor: str | None) -> HistoricoRecente:
    return HistoricoRecente(menor_preco_30_dias=p(menor) if menor else None, dias_acompanhado=dias)


def unico_evento(oferta: Oferta):
    eventos = oferta.coletar_eventos()
    assert len(eventos) == 1, eventos
    return eventos[0]


# --- Caso real: Gigabyte RTX 5060 EAGLE MAX, 18/11/2026 -----------------------
# O bot viu primeiro R$ 3.670,64, depois R$ 3.199,99; então a loja subiu para R$ 6.678,23.
# Um "de R$ 6.678
# por R$ 4.500" não é promoção: o preço já esteve bem mais baixo.


def test_de_inflado_e_barrado_quando_o_bot_ja_viu_preco_menor():
    oferta = Oferta("rtx", "kabum", p("3670.64"))  # primeiro preço que o bot viu

    oferta.registrar_preco(p("4500.00"), preco_de=p("6678.23"),
                           historico=acompanhado(10, menor="3199.99"))

    assert oferta.coletar_eventos() == []
    assert oferta.em_promocao is False


def test_de_vale_quando_o_preco_e_o_menor_dos_30_dias():
    oferta = Oferta("rtx", "kabum", p("3670.64"))  # primeiro preço que o bot viu

    oferta.registrar_preco(p("3100.00"), preco_de=p("6678.23"),
                           historico=acompanhado(10, menor="3199.99"))

    evento = unico_evento(oferta)
    assert evento.base_desconto == MENOR_30_DIAS
    assert evento.preco_referencia == Decimal("6678.23")


def test_voltar_ao_menor_preco_dos_30_dias_tambem_vale():
    oferta = Oferta("rtx", "kabum", p("3670.64"))  # primeiro preço que o bot viu

    oferta.registrar_preco(p("3199.99"), preco_de=p("6678.23"),
                           historico=acompanhado(10, menor="3199.99"))

    assert unico_evento(oferta).base_desconto == MENOR_30_DIAS


# --- Pouco histórico: o "de" passa, mas avisando a origem (opção B) ----------


def test_produto_novo_com_de_e_anunciado_como_informado_pela_loja():
    oferta = Oferta("1", "kabum", p("1000"))

    oferta.registrar_preco(p("1000"), preco_de=p("1250"))  # sem histórico

    evento = unico_evento(oferta)
    assert evento.base_desconto == PRECO_DE_LOJA
    assert evento.desconto_percentual == Decimal("20.00")


def test_menos_de_7_dias_nao_confere_mesmo_tendo_preco_menor():
    oferta = Oferta("1", "kabum", p("1000"))

    oferta.registrar_preco(p("1000"), preco_de=p("1250"),
                           historico=acompanhado(3, menor="800"))

    assert unico_evento(oferta).base_desconto == PRECO_DE_LOJA


def test_com_dias_mas_sem_preco_nos_ultimos_30_dias_nao_ha_como_conferir():
    oferta = Oferta("1", "kabum", p("1000"))

    oferta.registrar_preco(p("1000"), preco_de=p("1250"), historico=acompanhado(40, menor=None))

    assert unico_evento(oferta).base_desconto == PRECO_DE_LOJA


# --- Queda vista pelo próprio bot ----------------------------------------------


def test_queda_sobre_a_referencia_e_marcada_como_vista_pelo_bot():
    oferta = Oferta("1", "kabum", p("1000"))

    oferta.registrar_preco(p("800"), historico=acompanhado(10, menor="1000"))

    evento = unico_evento(oferta)
    assert evento.base_desconto == REFERENCIA
    assert evento.preco_referencia == Decimal("1000")


def test_de_inflado_barrado_nao_impede_promocao_pela_referencia():
    oferta = Oferta("1", "kabum", p("1000"))

    # "de" inflado (o bot já viu 700), mas o preço caiu 20% desde o primeiro visto.
    oferta.registrar_preco(p("800"), preco_de=p("2000"), historico=acompanhado(10, menor="700"))

    evento = unico_evento(oferta)
    assert evento.base_desconto == REFERENCIA
    assert evento.desconto_percentual == Decimal("20.00")


def test_em_empate_fica_a_referencia():
    oferta = Oferta("1", "kabum", p("1000"))

    oferta.registrar_preco(p("800"), preco_de=p("1000"))

    assert unico_evento(oferta).base_desconto == REFERENCIA


def test_entre_duas_bases_validas_vence_o_maior_desconto():
    oferta = Oferta("1", "kabum", p("1000"))

    oferta.registrar_preco(p("800"), preco_de=p("1600"), historico=acompanhado(10, menor="900"))

    evento = unico_evento(oferta)
    assert evento.base_desconto == MENOR_30_DIAS
    assert evento.desconto_percentual == Decimal("50.00")


# --- Elos isolados -------------------------------------------------------------


def test_desconto_minimo_recusa_abaixo_de_15():
    regra = DescontoMinimo(Decimal("15"))
    contexto = Contexto(p("100"), HistoricoRecente())

    assert regra.avaliar(Candidato(p("110"), TIPO_PRECO_DE, Decimal("14.99")), contexto) is None
    assert regra.avaliar(Candidato(p("120"), TIPO_PRECO_DE, Decimal("15")), contexto) is not None


# --- Histórico no repositório em memória ---------------------------------------


def test_repositorio_em_memoria_responde_menor_preco_e_dias_acompanhado():
    from datetime import datetime, timedelta, timezone

    from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria

    relogio = [datetime(2026, 11, 1, tzinfo=timezone.utc)]
    repositorio = OfertaRepositorioEmMemoria(agora=lambda: relogio[0])
    assert repositorio.historico_recente("rtx", "kabum") == HistoricoRecente()

    oferta = Oferta("rtx", "kabum", p("3670.64"))
    for dia, preco in ((0, "3670.64"), (5, "3199.99"), (8, "3499.99"), (40, "6678.23")):
        relogio[0] = datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=dia)
        oferta.registrar_preco(p(preco))
        repositorio.salvar(oferta)

    relogio[0] += timedelta(days=1)
    historico = repositorio.historico_recente("rtx", "kabum")
    assert historico.dias_acompanhado == 41
    # A janela começa no dia 11. O histórico guarda mudanças: 3.499,99 (dia 8) valeu
    # até o dia 40, então entra; 3.199,99 deixou de valer no dia 8, fora da janela.
    assert historico.menor_preco_30_dias == p("3499.99")


def test_repositorio_em_memoria_guarda_so_mudancas_e_o_preco_parado_continua_valendo():
    from datetime import datetime, timedelta, timezone

    from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria

    relogio = [datetime(2026, 11, 1, tzinfo=timezone.utc)]
    repositorio = OfertaRepositorioEmMemoria(agora=lambda: relogio[0])
    oferta = Oferta("rtx", "kabum", p("3199.99"))
    for dia in range(0, 45, 5):  # o mesmo preço, coletado a cada 5 dias
        relogio[0] = datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=dia)
        oferta.registrar_preco(p("3199.99"))
        repositorio.salvar(oferta)

    historico = repositorio.historico_recente("rtx", "kabum")
    # Uma linha só, do dia 0, fora da janela: o preço parado ainda é o menor dos 30 dias.
    assert historico.menor_preco_30_dias == p("3199.99")
    assert historico.dias_acompanhado == 40
