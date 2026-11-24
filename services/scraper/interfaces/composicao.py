"""Raiz de composição do scraper: o único lugar que escolhe as peças concretas.

Qual repositório, qual fonte de produtos, qual publicador e quais coletores de
loja, e como se ligam a cada rodada: tudo é decidido aqui. O agendador
(interfaces/agendador.py) cuida só da linha de comando, do .env e do laço das
rodadas; o resto do código recebe as peças prontas pelo construtor.
"""

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional

from application.conferencia import JaConfirmado, ReaproveitarSeNaoMudou, nada_confirmado
from application.portas import (
    TIPO_LISTAGEM,
    TIPO_PRODUTO,
    ColetorDePrecos,
    FonteDeProdutosMonitorados,
    PrecoColetado,
    ProdutoMonitorado,
    PublicadorDeEventos,
)
from application.processar_coleta import ProcessarColeta
from domain.repositorios import OfertaRepositorio
from infrastructure.mensageria.console import PublicadorNoConsole
from infrastructure.mensageria.redis_streams import PublicadorRedis
from infrastructure.persistencia.memoria import OfertaRepositorioEmMemoria
from infrastructure.persistencia.produtos_json import FonteDeProdutosJson
from infrastructure.scrapers.americanas import LOJA as AMERICANAS
from infrastructure.scrapers.americanas import ColetorAmericanas
from infrastructure.scrapers.americanas_listagem import ColetorListagemAmericanas
from infrastructure.scrapers.kabum import LOJA as KABUM
from infrastructure.scrapers.kabum import ColetorKabum
from infrastructure.scrapers.kabum_listagem import ColetorListagemKabum

logger = logging.getLogger(__name__)

ARQUIVO_PADRAO = Path(__file__).resolve().parent.parent / "produtos.json"

# Para adicionar uma loja: escreva o adaptador em infrastructure/scrapers e registre aqui,
# pela chave (loja, tipo). Uma loja pode ter coletor de produto avulso, de listagem ou os dois.
# A fábrica recebe também o "já confirmado?" (application/conferencia.py), usado por
# quem lê preços de uma listagem e confere produto a produto na página (hoje, a Kabum).
FabricaDeColetor = Callable[[list[ProdutoMonitorado], JaConfirmado], ColetorDePrecos]
FABRICAS_DE_COLETOR: dict[tuple[str, str], FabricaDeColetor] = {
    (KABUM, TIPO_PRODUTO): lambda itens, _: ColetorKabum(urls=[item.url for item in itens]),
    (KABUM, TIPO_LISTAGEM): lambda itens, ja_confirmado: ColetorListagemKabum(
        listagens=itens, ja_confirmado=ja_confirmado),
    (AMERICANAS, TIPO_PRODUTO): lambda itens, _: ColetorAmericanas(urls=[item.url for item in itens]),
    (AMERICANAS, TIPO_LISTAGEM): lambda itens, _: ColetorListagemAmericanas(listagens=itens),
}


class ColetorComposto(ColetorDePrecos):
    """Junta os coletores de todas as lojas num único ColetorDePrecos."""

    def __init__(self, coletores: list[ColetorDePrecos]):
        self.coletores = coletores

    def coletar(self) -> list[PrecoColetado]:
        itens: list[PrecoColetado] = []
        for coletor in self.coletores:
            itens.extend(coletor.coletar())
        return itens


def montar_coletor(
    produtos: list[ProdutoMonitorado],
    fabricas: dict[tuple[str, str], FabricaDeColetor] = FABRICAS_DE_COLETOR,
    ja_confirmado: JaConfirmado = nada_confirmado,
) -> ColetorComposto:
    """Agrupa os itens por (loja, tipo) e cria um coletor para cada grupo conhecido."""
    grupos: dict[tuple[str, str], list[ProdutoMonitorado]] = {}
    for produto in produtos:
        grupos.setdefault((produto.loja, produto.tipo), []).append(produto)

    coletores: list[ColetorDePrecos] = []
    for (loja, tipo), itens in grupos.items():
        fabrica = fabricas.get((loja, tipo))
        if fabrica is None:
            logger.warning(
                "Loja '%s' não tem scraper de %s; %d item(ns) ignorado(s)", loja, tipo, len(itens)
            )
            continue
        coletores.append(fabrica(itens, ja_confirmado))

    return ColetorComposto(coletores)


def limitar_produtos(produtos: list[ProdutoMonitorado], limite: int) -> list[ProdutoMonitorado]:
    """Rodada curta para teste: até `limite` endereços, alternando entre as lojas.

    Alternar evita que os primeiros da lista sejam todos da mesma loja. Listagens
    seguem só a primeira página, porque cada página já traz vários produtos.
    """
    por_loja: dict[str, list[ProdutoMonitorado]] = {}
    for produto in produtos:
        por_loja.setdefault(produto.loja, []).append(produto)
    escolhidos: list[ProdutoMonitorado] = []
    while len(escolhidos) < limite and any(por_loja.values()):
        for fila in por_loja.values():
            if fila and len(escolhidos) < limite:
                escolhidos.append(fila.pop(0))
    return [replace(p, paginas=1) if p.tipo == TIPO_LISTAGEM else p for p in escolhidos]


def executar_rodada(
    fonte: FonteDeProdutosMonitorados,
    repositorio: OfertaRepositorio,
    publicador: PublicadorDeEventos,
    fabricas: dict[tuple[str, str], FabricaDeColetor] = FABRICAS_DE_COLETOR,
    limite_urls: Optional[int] = None,
) -> int:
    """Uma rodada completa: lê a lista, coleta, processa e devolve quantas promoções saíram.

    Com limite_urls, coleta só esse tanto de endereços (veja limitar_produtos).
    """
    produtos = fonte.listar()
    if limite_urls is not None:
        produtos = limitar_produtos(produtos, limite_urls)
    coletor = montar_coletor(produtos, fabricas, ReaproveitarSeNaoMudou(repositorio))
    caso_de_uso = ProcessarColeta(coletor, repositorio, publicador)
    return caso_de_uso.executar()


def montar_publicador(redis_url: Optional[str]) -> PublicadorDeEventos:
    """Redis quando há URL configurada; console caso contrário."""
    if not redis_url:
        logger.info("REDIS_URL não definida: promoções serão impressas no console")
        return PublicadorNoConsole()

    import redis  # importado aqui para que o console funcione mesmo sem o pacote

    cliente = redis.from_url(redis_url, decode_responses=True)
    cliente.ping()  # falha já na partida se o Redis não estiver acessível
    logger.info("Publicando promoções no Redis")
    return PublicadorRedis(cliente)


class ConexaoSobDemanda:
    """Factory Method aplicado à conexão: entrega sempre uma conexão viva.

    A conexão PostgreSQL fica ociosa entre as rodadas e pode ser derrubada pelo
    servidor, pela rede ou por um reinício do container. Antes de cada rodada,
    se a anterior estiver fechada ou quebrada, ela é descartada e a fábrica
    abre outra. Se o banco ainda estiver fora do ar, o erro sobe para a rodada,
    e a próxima chamada tenta de novo.
    """

    def __init__(self, fabrica: Callable[[], Any]):
        self._fabrica = fabrica
        self._conexao: Any = None

    def obter(self) -> Any:
        conexao = self._conexao
        if conexao is None or conexao.closed or getattr(conexao, "broken", False):
            if conexao is not None:
                logger.warning("Conexão PostgreSQL perdida; abrindo uma nova")
            self.fechar()
            self._conexao = self._fabrica()
        return self._conexao

    def fechar(self) -> None:
        conexao, self._conexao = self._conexao, None
        if conexao is None:
            return
        try:
            conexao.close()
        except Exception:
            pass  # já estava quebrada; não há o que liberar


PERSISTENCIAS = ("memoria", "postgres")
FONTES_DE_PRODUTOS = ("json", "postgres")
TRANSPORTES_DE_EVENTOS = ("console", "redis", "postgres")


class ConfiguracaoInvalida(ValueError):
    """Combinação de opções que não dá para montar."""


@dataclass(frozen=True)
class Configuracao:
    """As escolhas de uma execução, já lidas da linha de comando e do ambiente."""

    persistencia: str = "postgres"
    fonte_produtos: str = "json"
    eventos: str = "console"
    produtos: Path = ARQUIVO_PADRAO
    redis_url: Optional[str] = None
    database_url: str = ""
    limite_urls: Optional[int] = None

    @property
    def usa_postgres(self) -> bool:
        return self.persistencia == "postgres" or self.fonte_produtos == "postgres"

    def validar(self) -> None:
        for nome, valor, permitidos in (
            ("PERSISTENCIA", self.persistencia, PERSISTENCIAS),
            ("FONTE_PRODUTOS", self.fonte_produtos, FONTES_DE_PRODUTOS),
            ("EVENTOS_TRANSPORTE", self.eventos, TRANSPORTES_DE_EVENTOS),
        ):
            if valor not in permitidos:
                raise ConfiguracaoInvalida(f"{nome} inválida: escolha {', '.join(permitidos)}")
        if self.eventos == "postgres" and self.persistencia != "postgres":
            raise ConfiguracaoInvalida("--eventos postgres exige --persistencia postgres")
        if self.eventos == "redis" and not self.redis_url:
            raise ConfiguracaoInvalida("--eventos redis exige REDIS_URL ou --redis-url")


class Montagem:
    """Monta as peças da configuração e entrega uma rodada pronta para o laço.

    iniciar() abre o que precisa durar a execução inteira (e falha já na
    partida se a configuração estiver errada); rodada() monta, sobre uma
    conexão viva, as peças ligadas ao banco e roda uma coleta; fechar() libera
    a conexão.
    """

    def __init__(
        self,
        config: Configuracao,
        fabricas: dict[tuple[str, str], FabricaDeColetor] = FABRICAS_DE_COLETOR,
    ):
        self.config = config
        self._fabricas = fabricas
        self._conexoes: Optional[ConexaoSobDemanda] = None
        self._repositorio_memoria: Optional[OfertaRepositorioEmMemoria] = None
        self._publicador_fixo: Optional[PublicadorDeEventos] = None

    def iniciar(self) -> None:
        config = self.config
        if config.usa_postgres:
            from infrastructure.persistencia import postgres

            self._conexoes = ConexaoSobDemanda(lambda: postgres.conectar(config.database_url))
            self._conexoes.obter()  # configuração errada derruba já na partida

        # O que não depende da conexão é criado uma vez: a memória precisa durar entre
        # rodadas, e o cliente Redis já reconecta sozinho no próximo comando.
        if config.persistencia == "memoria":
            self._repositorio_memoria = OfertaRepositorioEmMemoria()
        if config.eventos != "postgres":
            self._publicador_fixo = montar_publicador(
                config.redis_url if config.eventos == "redis" else None
            )

    def rodada(self) -> int:
        # Peças ligadas ao banco são montadas a cada rodada sobre uma conexão viva.
        conexao = self._conexoes.obter() if self._conexoes else None
        return executar_rodada(
            self._fonte(conexao),
            self._repositorio(conexao),
            self._publicador(conexao),
            fabricas=self._fabricas,
            limite_urls=self.config.limite_urls,
        )

    def fechar(self) -> None:
        if self._conexoes is not None:
            self._conexoes.fechar()

    def _fonte(self, conexao) -> FonteDeProdutosMonitorados:
        if self.config.fonte_produtos == "postgres":
            from infrastructure.persistencia.postgres import FonteDeProdutosPostgres
            return FonteDeProdutosPostgres(conexao)
        return FonteDeProdutosJson(self.config.produtos)

    def _repositorio(self, conexao) -> OfertaRepositorio:
        if self.config.persistencia == "postgres":
            from infrastructure.persistencia.postgres import OfertaRepositorioPostgres
            return OfertaRepositorioPostgres(conexao)
        return self._repositorio_memoria

    def _publicador(self, conexao) -> PublicadorDeEventos:
        if self.config.eventos == "postgres":
            from infrastructure.mensageria.postgres import PublicadorPostgres
            return PublicadorPostgres(conexao)
        return self._publicador_fixo
