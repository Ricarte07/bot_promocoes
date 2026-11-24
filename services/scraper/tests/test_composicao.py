import json
from decimal import Decimal

import pytest

from application.portas import ColetorDePrecos, PrecoColetado
from domain.preco import Preco
from infrastructure.mensageria.console import PublicadorNoConsole
from interfaces.composicao import Configuracao, ConfiguracaoInvalida, Montagem


# --- Configuracao.validar ------------------------------------------------------


@pytest.mark.parametrize("opcoes, mensagem", [
    ({"persistencia": "arquivo"}, "PERSISTENCIA inválida"),
    ({"fonte_produtos": "planilha"}, "FONTE_PRODUTOS inválida"),
    ({"eventos": "email"}, "EVENTOS_TRANSPORTE inválida"),
    ({"persistencia": "memoria", "eventos": "postgres"}, "--eventos postgres exige"),
    ({"eventos": "redis", "redis_url": ""}, "--eventos redis exige"),
])
def test_configuracao_recusa_combinacoes_que_nao_dao_para_montar(opcoes, mensagem):
    with pytest.raises(ConfiguracaoInvalida, match=mensagem):
        Configuracao(**opcoes).validar()


def test_configuracao_valida_passa():
    Configuracao(persistencia="memoria", eventos="redis", redis_url="redis://x").validar()
    Configuracao(persistencia="postgres", eventos="postgres").validar()


def test_so_usa_postgres_quando_alguma_peca_pede():
    assert not Configuracao(persistencia="memoria", fonte_produtos="json").usa_postgres
    assert Configuracao(persistencia="memoria", fonte_produtos="postgres").usa_postgres
    assert Configuracao(persistencia="postgres").usa_postgres


# --- Montagem: tudo ligado, sem rede nem banco ---------------------------------


class ColetorComPrecos(ColetorDePrecos):
    """Devolve, a cada rodada, o próximo preço da lista para cada URL."""

    def __init__(self, urls, precos):
        self.urls, self.precos = urls, precos

    def coletar(self):
        valor = self.precos.pop(0)
        return [PrecoColetado(url, "kabum", Preco(Decimal(valor))) for url in self.urls]


def test_montagem_em_memoria_guarda_entre_rodadas_e_publica_a_queda(tmp_path, monkeypatch):
    produtos = tmp_path / "produtos.json"
    produtos.write_text(json.dumps([{"loja": "kabum", "url": "k1"}]), encoding="utf-8")
    precos = ["1000", "800"]
    fabricas = {("kabum", "produto"): lambda itens, _: ColetorComPrecos([i.url for i in itens], precos)}
    mensagens: list[str] = []
    monkeypatch.setattr("interfaces.composicao.montar_publicador",
                        lambda _url: PublicadorNoConsole(escrever=mensagens.append))

    montagem = Montagem(Configuracao(persistencia="memoria", fonte_produtos="json",
                                     eventos="console", produtos=produtos), fabricas)
    montagem.iniciar()
    try:
        assert montagem.rodada() == 0  # primeiro preço visto: vira referência
        assert montagem.rodada() == 1  # caiu 20%: a memória durou entre as rodadas
    finally:
        montagem.fechar()

    assert len(mensagens) == 1 and "20.00%" in mensagens[0]


def test_montagem_com_postgres_falha_ja_na_partida(monkeypatch):
    import infrastructure.persistencia.postgres as postgres

    def recusar(_url):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(postgres, "conectar", recusar)
    montagem = Montagem(Configuracao(persistencia="postgres", eventos="console"))

    with pytest.raises(RuntimeError, match="fora do ar"):
        montagem.iniciar()
    montagem.fechar()  # nada aberto: não pode lançar
