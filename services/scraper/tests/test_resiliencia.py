"""O scraper contínuo sobrevive a uma rodada com erro e reabre a conexão que caiu."""

import pytest

import interfaces.agendador as agendador
from interfaces.agendador import ConexaoSobDemanda, executar_em_laco


class Parar(Exception):
    """Interrompe o laço infinito nos testes, vinda da função de espera."""


def espera_que_para_depois_de(vezes: int, esperas: list):
    def esperar(segundos):
        esperas.append(segundos)
        if len(esperas) >= vezes:
            raise Parar()
    return esperar


class ConexaoFalsa:
    def __init__(self):
        self.closed = False
        self.broken = False
        self.fechamentos = 0

    def close(self):
        self.closed = True
        self.fechamentos += 1


# --- executar_em_laco --------------------------------------------------------


def test_rodada_com_erro_nao_derruba_o_laco_e_a_seguinte_roda(caplog):
    chamadas = []

    def rodada():
        chamadas.append(1)
        if len(chamadas) == 1:
            raise ConnectionError("banco caiu")
        return 2

    esperas = []
    with pytest.raises(Parar):
        executar_em_laco(rodada, intervalo_segundos=1800,
                         esperar=espera_que_para_depois_de(2, esperas))

    assert len(chamadas) == 2
    assert "ConnectionError" in caplog.text
    # Depois de uma falha tenta de novo em 1 minuto; depois de um sucesso, no intervalo normal.
    assert esperas == [60, 1800]


def test_intervalo_menor_que_um_minuto_vale_tambem_depois_de_falha():
    def rodada():
        raise RuntimeError("falhou")

    esperas = []
    with pytest.raises(Parar):
        executar_em_laco(rodada, intervalo_segundos=30,
                         esperar=espera_que_para_depois_de(1, esperas))

    assert esperas == [30]


def test_log_de_falha_nao_mostra_a_mensagem_do_erro(caplog):
    def rodada():
        raise RuntimeError("postgresql://usuario:senha-secreta@host/banco")

    with pytest.raises(Parar):
        executar_em_laco(rodada, intervalo_segundos=60,
                         esperar=espera_que_para_depois_de(1, []))

    assert "senha-secreta" not in caplog.text


def test_uma_vez_repassa_o_erro_para_encerrar_com_falha():
    def rodada():
        raise ConnectionError("banco caiu")

    with pytest.raises(ConnectionError):
        executar_em_laco(rodada, intervalo_segundos=60, uma_vez=True,
                         esperar=lambda _: pytest.fail("não deveria esperar"))


def test_uma_vez_com_sucesso_nao_espera():
    executar_em_laco(lambda: 0, intervalo_segundos=60, uma_vez=True,
                     esperar=lambda _: pytest.fail("não deveria esperar"))


# --- ConexaoSobDemanda (fábrica de conexão) ----------------------------------


def test_reaproveita_a_conexao_enquanto_ela_esta_viva():
    abertas = []
    conexoes = ConexaoSobDemanda(lambda: abertas.append(ConexaoFalsa()) or abertas[-1])

    primeira = conexoes.obter()
    segunda = conexoes.obter()

    assert primeira is segunda
    assert len(abertas) == 1


@pytest.mark.parametrize("estado", ["closed", "broken"])
def test_abre_outra_quando_a_anterior_caiu(estado):
    abertas = []
    conexoes = ConexaoSobDemanda(lambda: abertas.append(ConexaoFalsa()) or abertas[-1])
    antiga = conexoes.obter()
    setattr(antiga, estado, True)

    nova = conexoes.obter()

    assert nova is not antiga
    assert len(abertas) == 2
    assert antiga.closed  # a quebrada é fechada para não vazar recurso


def test_falha_ao_reabrir_propaga_e_tenta_de_novo_na_proxima():
    tentativas = []

    def fabrica():
        tentativas.append(1)
        if len(tentativas) == 1:
            raise RuntimeError("ainda fora do ar")
        return ConexaoFalsa()

    conexoes = ConexaoSobDemanda(fabrica)
    with pytest.raises(RuntimeError):
        conexoes.obter()
    assert conexoes.obter() is not None
    assert len(tentativas) == 2


def test_fechar_ignora_erro_da_conexao_ja_quebrada():
    class QuebraAoFechar(ConexaoFalsa):
        def close(self):
            raise OSError("socket já fechado")

    conexoes = ConexaoSobDemanda(QuebraAoFechar)
    conexoes.obter()
    conexoes.fechar()  # não pode lançar


# --- main: tudo ligado ---------------------------------------------------------


def test_main_continuo_reconecta_depois_que_a_conexao_cai(monkeypatch):
    abertas = []

    def conectar_falso(_url):
        abertas.append(ConexaoFalsa())
        return abertas[-1]

    rodadas = []

    def rodada_falsa(fonte, repositorio, publicador):
        rodadas.append(repositorio.conexao)
        if len(rodadas) == 1:
            repositorio.conexao.broken = True  # o banco derrubou a conexão no meio
            raise ConnectionError("server closed the connection unexpectedly")
        return 0

    import infrastructure.persistencia.postgres as postgres
    monkeypatch.setattr(postgres, "conectar", conectar_falso)
    monkeypatch.setattr(agendador, "executar_rodada", rodada_falsa)
    monkeypatch.setattr(agendador.time, "sleep", espera_que_para_depois_de(2, []))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:s@localhost/promo")

    with pytest.raises(SystemExit):  # Parar sai pelo tratamento geral do main
        agendador.main(["--persistencia", "postgres", "--eventos", "console"])

    assert len(rodadas) == 2
    assert rodadas[0] is abertas[0]
    assert rodadas[1] is abertas[1]  # a segunda rodada usou uma conexão nova
    assert abertas[0].closed and abertas[1].closed  # a nova é fechada ao sair
