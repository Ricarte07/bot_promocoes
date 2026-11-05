import pytest

from infrastructure.persistencia.postgres import conectar
from interfaces.agendador import main


def test_postgres_sem_url_nao_usa_memoria():
    with pytest.raises(ValueError, match='DATABASE_URL'):
        conectar('')


def test_configuracao_impede_fila_postgres_com_memoria():
    with pytest.raises(SystemExit) as erro:
        main(['--persistencia', 'memoria', '--eventos', 'postgres'])
    assert erro.value.code == 2


def test_configuracao_impede_redis_sem_url(monkeypatch):
    monkeypatch.setenv('REDIS_URL', '')
    with pytest.raises(SystemExit) as erro:
        main(['--persistencia', 'memoria', '--eventos', 'redis'])
    assert erro.value.code == 2


def test_falha_postgres_sem_fallback(monkeypatch, caplog):
    monkeypatch.setenv('DATABASE_URL', '')
    with pytest.raises(SystemExit) as erro:
        main(['--persistencia', 'postgres', '--eventos', 'console', '--uma-vez'])
    assert erro.value.code == 1
    assert 'Não houve troca automática para memória' in caplog.text


def test_falha_de_conexao_nao_expoe_credenciais(monkeypatch):
    import psycopg
    def falhar(**opcoes):
        raise psycopg.OperationalError('senha-secreta que não deve aparecer')
    monkeypatch.setattr(psycopg, 'connect', falhar)
    with pytest.raises(RuntimeError, match='Não foi possível conectar') as erro:
        conectar('postgresql://usuario:senha-secreta@db.exemplo.com/postgres?sslmode=require')
    assert 'senha-secreta' not in str(erro.value)


def test_conexao_remota_exige_ssl():
    with pytest.raises(ValueError, match='sslmode'):
        conectar('postgresql://usuario:senha@db.exemplo.com/postgres?sslmode=disable')
