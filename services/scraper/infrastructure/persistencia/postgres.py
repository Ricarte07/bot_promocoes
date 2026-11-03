"""Adaptadores PostgreSQL. A conexão fica apenas nos serviços, nunca no navegador."""

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict

from application.portas import FonteDeProdutosMonitorados, ProdutoMonitorado
from domain.cupom import Cupom
from domain.oferta import Oferta
from domain.preco import Preco
from domain.repositorios import OfertaRepositorio


def conectar(database_url: str):
    if not database_url:
        raise ValueError("PostgreSQL selecionado: defina DATABASE_URL no .env ou ambiente")
    try:
        parametros = conninfo_to_dict(database_url)
        host = parametros.get('host', '')
        if host and not host.startswith('/') and host not in ('localhost', '127.0.0.1', '::1'):
            if parametros.get('sslmode', 'require') not in ('require', 'verify-ca', 'verify-full'):
                raise ValueError("Conexão PostgreSQL remota exige sslmode=require ou verify-full")
            parametros.setdefault('sslmode', 'require')
        return psycopg.connect(
            **parametros, autocommit=True, row_factory=dict_row,
            connect_timeout=10, prepare_threshold=None,
            options="-c statement_timeout=15000 -c lock_timeout=10000",
        )
    except psycopg.Error:
        # Não imprimir DSN/senha, inclusive quando a URL for inválida.
        raise RuntimeError(
            "Não foi possível conectar ao PostgreSQL. Confira DATABASE_URL, SSL, "
            "senha, rede e o modo de conexão do Supabase. Nenhum modo memória foi ativado."
        ) from None


class OfertaRepositorioPostgres(OfertaRepositorio):
    def __init__(self, conexao):
        self.conexao = conexao

    @contextmanager
    def transacao(self, produto_id: str, loja: str):
        with self.conexao.transaction():
            # Também serializa a primeira coleta, quando ainda não existe linha para FOR UPDATE.
            self.conexao.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"{len(loja)}:{loja}{produto_id}",),
            )
            yield

    def buscar(self, produto_id: str, loja: str):
        row = self.conexao.execute(
            "SELECT * FROM public.ofertas WHERE produto_id=%s AND loja=%s",
            (produto_id, loja),
        ).fetchone()
        if row is None:
            return None
        oferta = Oferta(produto_id, loja, Preco(row['preco_referencia']), row['nome'], row['url'])
        # Reidratar sem registrar_preco: carregar estado não é uma nova coleta/evento.
        oferta.preco_atual = Preco(row['preco_atual'])
        oferta.preco_de = Preco(row['preco_de']) if row['preco_de'] is not None else None
        oferta.preco_final = Preco(row['preco_final'])
        oferta.cupom = Cupom(row['cupom_codigo'], row['cupom_desconto_percentual']) if row['cupom_codigo'] else None
        oferta.em_promocao = row['em_promocao']
        return oferta

    def salvar(self, oferta: Oferta) -> None:
        codigo = oferta.cupom.codigo if oferta.cupom else None
        percentual = oferta.cupom.desconto_percentual if oferta.cupom else None
        preco_de = oferta.preco_de.valor if oferta.preco_de else None
        with self.conexao.transaction():
            self.conexao.execute(
                """INSERT INTO public.ofertas
                (loja,produto_id,nome,url,preco_referencia,preco_atual,preco_de,
                 preco_final,cupom_codigo,cupom_desconto_percentual,em_promocao)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (loja,produto_id) DO UPDATE SET
                nome=EXCLUDED.nome,url=EXCLUDED.url,preco_atual=EXCLUDED.preco_atual,
                preco_de=EXCLUDED.preco_de,preco_final=EXCLUDED.preco_final,
                cupom_codigo=EXCLUDED.cupom_codigo,
                cupom_desconto_percentual=EXCLUDED.cupom_desconto_percentual,
                em_promocao=EXCLUDED.em_promocao,atualizada_em=clock_timestamp()""",
                (oferta.loja, oferta.produto_id, oferta.nome, oferta.url,
                 oferta.preco_referencia.valor, oferta.preco_atual.valor, preco_de,
                 oferta.preco_final.valor, codigo, percentual, oferta.em_promocao),
            )
            self.conexao.execute(
                """INSERT INTO public.historico_precos
                (loja,produto_id,preco,preco_de,preco_final,cupom_codigo,cupom_desconto_percentual)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (oferta.loja, oferta.produto_id, oferta.preco_atual.valor, preco_de,
                 oferta.preco_final.valor, codigo, percentual),
            )


class FonteDeProdutosPostgres(FonteDeProdutosMonitorados):
    def __init__(self, conexao):
        self.conexao = conexao

    def listar(self) -> list[ProdutoMonitorado]:
        rows = self.conexao.execute(
            "SELECT loja,url,tipo,paginas FROM public.produtos_monitorados WHERE ativo ORDER BY id"
        ).fetchall()
        return [ProdutoMonitorado(**row) for row in rows]
