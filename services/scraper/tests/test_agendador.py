from decimal import Decimal

from application.portas import (
    ColetorDePrecos,
    FonteDeProdutosMonitorados,
    PrecoColetado,
    ProdutoMonitorado,
)
from domain.cupom import Cupom
from domain.eventos import PromocaoDetectada
from domain.preco import Preco
from infrastructure.mensageria.console import PublicadorNoConsole
from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria
from infrastructure.mensageria.redis_streams import PublicadorRedis
from interfaces.agendador import (
    carregar_dotenv,
    executar_rodada,
    montar_coletor,
    montar_publicador,
)


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


def test_sem_redis_url_publica_no_console():
    assert isinstance(montar_publicador(None), PublicadorNoConsole)
    assert isinstance(montar_publicador(""), PublicadorNoConsole)


def test_com_redis_url_publica_no_redis(monkeypatch):
    class RedisFalso:
        def __init__(self):
            self.pingou = False

        def ping(self):
            self.pingou = True

    import redis

    falso = RedisFalso()
    monkeypatch.setattr(redis, "from_url", lambda url, **_: falso)

    publicador = montar_publicador("redis://localhost:6379/0")

    assert isinstance(publicador, PublicadorRedis)
    assert falso.pingou is True


def test_mensagem_no_console_mostra_cupom_e_preco_final():
    mensagens: list[str] = []
    publicador = PublicadorNoConsole(escrever=mensagens.append)

    publicador.publicar(
        PromocaoDetectada(
            produto_id="1",
            loja="kabum",
            preco_atual=Decimal("1000"),
            preco_referencia=Decimal("1000"),
            desconto_percentual=Decimal("15.00"),
            nome="Notebook X",
            cupom=Cupom("QUINZE", Decimal("15")),
        )
    )

    assert mensagens == [
        "[PROMOÇÃO] kabum | Notebook X | de R$ 1000 por R$ 850.00 com o cupom QUINZE "
        "(15.00% de desconto)"
    ]


# --- .env -----------------------------------------------------------------------


def test_dotenv_define_variaveis_que_nao_existem(tmp_path, monkeypatch):
    monkeypatch.delenv("TESTE_REDIS_URL", raising=False)
    monkeypatch.delenv("TESTE_TOKEN", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "# comentário\n"
        "TESTE_REDIS_URL=redis://localhost:6379/0\n"
        'TESTE_TOKEN="abc:123"\n'
        "\n"
        "linha sem igual\n",
        encoding="utf-8",
    )

    carregar_dotenv(env)

    import os

    assert os.environ["TESTE_REDIS_URL"] == "redis://localhost:6379/0"
    assert os.environ["TESTE_TOKEN"] == "abc:123"  # aspas removidas


def test_dotenv_nao_sobrescreve_variavel_ja_definida(tmp_path, monkeypatch):
    monkeypatch.setenv("TESTE_REDIS_URL", "redis://ja-definida:6379/0")
    env = tmp_path / ".env"
    env.write_text("TESTE_REDIS_URL=redis://do-arquivo:6379/0\n", encoding="utf-8")

    carregar_dotenv(env)

    import os

    assert os.environ["TESTE_REDIS_URL"] == "redis://ja-definida:6379/0"


def test_dotenv_inexistente_nao_e_erro(tmp_path):
    carregar_dotenv(tmp_path / "nao-existe.env")
