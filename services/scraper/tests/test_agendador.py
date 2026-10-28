from decimal import Decimal

from application.portas import (
    ColetorDePrecos,
    FonteDeProdutosMonitorados,
    PrecoColetado,
    ProdutoMonitorado,
)
from domain.eventos import PromocaoDetectada
from domain.preco import Preco
from infrastructure.mensageria.console import PublicadorNoConsole
from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria
from interfaces.agendador import executar_rodada, montar_coletor


class ColetorFalso(ColetorDePrecos):
    """Finge ser o scraper de uma loja: devolve um preço fixo para cada URL recebida."""

    def __init__(self, loja: str, urls: list[str], valor: str):
        self.loja = loja
        self.urls = urls
        self.valor = valor

    def coletar(self):
        return [PrecoColetado(url, self.loja, Preco(Decimal(self.valor))) for url in self.urls]


class FonteFalsa(FonteDeProdutosMonitorados):
    def __init__(self, produtos):
        self.produtos = produtos

    def listar(self):
        return self.produtos


def fabricas_com_preco(valor: str):
    return {
        "kabum": lambda urls: ColetorFalso("kabum", urls, valor),
        "outra": lambda urls: ColetorFalso("outra", urls, valor),
    }


def test_agrupa_urls_por_loja_e_cria_um_coletor_por_loja():
    produtos = [
        ProdutoMonitorado("kabum", "k1"),
        ProdutoMonitorado("outra", "o1"),
        ProdutoMonitorado("kabum", "k2"),
    ]

    composto = montar_coletor(produtos, fabricas_com_preco("100"))

    por_loja = {c.loja: c.urls for c in composto.coletores}
    assert por_loja == {"kabum": ["k1", "k2"], "outra": ["o1"]}


def test_loja_sem_scraper_e_ignorada_sem_quebrar():
    produtos = [ProdutoMonitorado("kabum", "k1"), ProdutoMonitorado("desconhecida", "d1")]

    composto = montar_coletor(produtos, fabricas_com_preco("100"))

    assert [c.loja for c in composto.coletores] == ["kabum"]
    assert [item.produto_id for item in composto.coletar()] == ["k1"]


def test_rodada_completa_publica_promocao_na_segunda_coleta():
    fonte = FonteFalsa([ProdutoMonitorado("kabum", "k1")])
    repositorio = OfertaRepositorioEmMemoria()
    mensagens: list[str] = []
    publicador = PublicadorNoConsole(escrever=mensagens.append)

    primeira = executar_rodada(fonte, repositorio, publicador, fabricas_com_preco("1000"))
    segunda = executar_rodada(fonte, repositorio, publicador, fabricas_com_preco("800"))

    assert (primeira, segunda) == (0, 1)
    assert len(mensagens) == 1
    assert "kabum" in mensagens[0]
    assert "20.00%" in mensagens[0]


def test_mensagem_no_console_mostra_nome_e_link():
    mensagens: list[str] = []
    publicador = PublicadorNoConsole(escrever=mensagens.append)

    publicador.publicar(
        PromocaoDetectada(
            produto_id="1",
            loja="kabum",
            preco_atual=Decimal("800"),
            preco_referencia=Decimal("1000"),
            desconto_percentual=Decimal("20.00"),
            nome="Notebook X",
            url="https://www.kabum.com.br/produto/1/notebook-x",
        )
    )

    assert mensagens == [
        "[PROMOÇÃO] kabum | Notebook X | de R$ 1000 por R$ 800 (20.00% de desconto) "
        "https://www.kabum.com.br/produto/1/notebook-x"
    ]
