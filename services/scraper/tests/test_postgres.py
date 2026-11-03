"""Integração real, opt-in: TEST_DATABASE_URL deve apontar a um banco *_test.

Cria um banco descartável por teste; exige CREATEDB. Nunca limpa tabelas existentes.
Não usa rede de lojas, Redis, Telegram ou WhatsApp.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from application.portas import PrecoColetado
from application.processar_coleta import ProcessarColeta
from domain.cupom import Cupom
from domain.preco import Preco
from infrastructure.mensageria.console import PublicadorNoConsole
from infrastructure.mensageria.postgres import PublicadorPostgres
from infrastructure.mensageria.redis_streams import PublicadorRedis
from infrastructure.persistencia.postgres import (
    FonteDeProdutosPostgres, OfertaRepositorioPostgres, conectar,
)


@pytest.fixture
def banco():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Defina TEST_DATABASE_URL para testar PostgreSQL real e isolado')
    config = conninfo_to_dict(url)
    if not config.get('dbname', '').endswith('_test'):
        pytest.fail('TEST_DATABASE_URL deve apontar a um banco com sufixo _test')
    nome = f'bot_promocoes_{uuid4().hex}_test'
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(nome)))
        teste_url = make_conninfo(url, dbname=nome)
        try:
            with conectar(teste_url) as c:
                c.execute((Path(__file__).resolve().parents[3] / 'sql/schema.sql').read_text())
            yield teste_url
        finally:
            # Somente o banco de nome aleatório criado acima é removido.
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(nome)))


def item(valor='100', cupom=None, preco_de=None, produto_id='descoberto'):
    return PrecoColetado(produto_id, 'kabum', Preco(Decimal(valor)), 'Nome coletado',
                         f'https://www.kabum.com.br/produto/{produto_id}/produto', cupom,
                         Preco(Decimal(preco_de)) if preco_de else None)


def coletar(c, observacoes, publicador=None):
    class Coletor:
        def coletar(self):
            return observacoes
    return ProcessarColeta(Coletor(), OfertaRepositorioPostgres(c),
                           publicador or PublicadorPostgres(c)).executar()


def test_reinicio_historico_cupons_sem_repetir_promocao(banco):
    with conectar(banco) as c:
        assert coletar(c, [item()]) == 0
        assert coletar(c, [item('90', Cupom('VINTE', Decimal('20')), '110')]) == 1
    # Nova conexão e novo repositório: simula reinício, sem referência em memória.
    with conectar(banco) as c:
        oferta = OfertaRepositorioPostgres(c).buscar('descoberto', 'kabum')
        assert oferta.preco_referencia.valor == Decimal('100')
        assert oferta.preco_atual.valor == Decimal('90')
        assert oferta.preco_final.valor == Decimal('72.00')
        assert oferta.preco_de.valor == Decimal('110')
        assert oferta.cupom == Cupom('VINTE', Decimal('20'))
        assert oferta.em_promocao
        assert oferta.nome == 'Nome coletado'
        assert oferta.url.endswith('/descoberto/produto')
        assert coletar(c, [item('90', Cupom('VINTE', Decimal('20')), '110')]) == 0
        assert c.execute('SELECT count(*) AS n FROM public.historico_precos').fetchone()['n'] == 3
        rows = c.execute('SELECT payload FROM public.eventos_pendentes').fetchall()
        assert len(rows) == 1
        assert rows[0]['payload']['versao'] == 2
        assert rows[0]['payload']['preco_final'] == '72.00'
        # Cupom sem condição de desconto permanece desconhecido; cupom ausente é removido.
        assert coletar(c, [item('70', Cupom('CODIGO'))]) == 1
        assert OfertaRepositorioPostgres(c).buscar('descoberto', 'kabum').cupom.desconto_percentual is None
        coletar(c, [item('70')])
        assert OfertaRepositorioPostgres(c).buscar('descoberto', 'kabum').cupom is None


def test_rollback_oferta_historico_e_evento(banco):
    with conectar(banco) as c:
        coletar(c, [item()])
        class FalhaDepoisDeInserir(PublicadorPostgres):
            def publicar(self, evento):
                super().publicar(evento)
                raise RuntimeError('falha simulada depois do INSERT do evento')
        with pytest.raises(RuntimeError, match='falha simulada'):
            coletar(c, [item('80')], FalhaDepoisDeInserir(c))
        assert OfertaRepositorioPostgres(c).buscar('descoberto', 'kabum').preco_atual.valor == Decimal('100')
        assert c.execute('SELECT count(*) AS n FROM public.historico_precos').fetchone()['n'] == 1
        assert c.execute('SELECT count(*) AS n FROM public.eventos_pendentes').fetchone()['n'] == 0
        assert coletar(c, [item('80')]) == 1
        assert c.execute('SELECT count(*) AS n FROM public.historico_precos').fetchone()['n'] == 2
        assert c.execute('SELECT count(*) AS n FROM public.eventos_pendentes').fetchone()['n'] == 1


def test_fonte_categoria_e_produtos_descobertos_individuais(banco):
    from interfaces.agendador import executar_rodada
    with conectar(banco) as c:
        c.execute("INSERT INTO public.produtos_monitorados (loja,url,tipo,paginas) VALUES ('kabum','https://www.kabum.com.br/hardware','listagem',2)")
        fonte = FonteDeProdutosPostgres(c)
        assert fonte.listar()[0].paginas == 2
        class Listagem:
            def coletar(self):
                return [item(produto_id='1'), item(produto_id='2')]
        fabricas = {('kabum', 'listagem'): lambda _: Listagem()}
        executar_rodada(fonte, OfertaRepositorioPostgres(c), PublicadorPostgres(c), fabricas)
        assert c.execute('SELECT count(*) AS n FROM public.ofertas').fetchone()['n'] == 2
        assert c.execute('SELECT count(*) AS n FROM public.historico_precos').fetchone()['n'] == 2


def test_console_e_redis_com_persistencia(banco):
    mensagens = []
    class RedisFalso:
        def xadd(self, stream, fields, **opcoes):
            mensagens.append((stream, fields))
    with conectar(banco) as c:
        coletar(c, [item()])
        assert coletar(c, [item('80')], PublicadorNoConsole(escrever=mensagens.append)) == 1
        assert coletar(c, [item('60')], PublicadorRedis(RedisFalso())) == 1
        assert len(mensagens) == 2
        assert mensagens[1][0] == 'promocoes'
        assert c.execute('SELECT count(*) AS n FROM public.eventos_pendentes').fetchone()['n'] == 0


def test_coletores_concorrentes_nao_repetem_evento(banco):
    def rodada():
        with conectar(banco) as c:
            return coletar(c, [item('80', preco_de='100')])
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: rodada(), range(2))) == [0, 1]
    with conectar(banco) as c:
        assert c.execute('SELECT count(*) AS n FROM public.ofertas').fetchone()['n'] == 1
        assert c.execute('SELECT count(*) AS n FROM public.historico_precos').fetchone()['n'] == 2
        assert c.execute('SELECT count(*) AS n FROM public.eventos_pendentes').fetchone()['n'] == 1


def test_rls_e_permissoes_publicas(banco):
    with conectar(banco) as c:
        rows = c.execute("SELECT relrowsecurity FROM pg_class WHERE oid IN ('public.ofertas'::regclass,'public.historico_precos'::regclass,'public.produtos_monitorados'::regclass,'public.eventos_pendentes'::regclass)").fetchall()
        assert len(rows) == 4 and all(row['relrowsecurity'] for row in rows)
        c.execute('CREATE ROLE visitante_bot_sem_acesso')
        try:
            with c.transaction():
                c.execute('SET LOCAL ROLE visitante_bot_sem_acesso')
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with c.transaction():
                        c.execute('SELECT * FROM public.ofertas')
        finally:
            c.execute('DROP ROLE visitante_bot_sem_acesso')
