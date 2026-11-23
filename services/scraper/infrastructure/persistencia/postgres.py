"""Adaptadores PostgreSQL. A conexão fica apenas nos serviços, nunca no navegador."""

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict

from application.portas import FonteDeProdutosMonitorados, ProdutoMonitorado
from domain.cupom import Cupom
from domain.oferta import Oferta
from domain.preco import Preco
from domain.regras_promocao import HistoricoRecente
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

    def buscar_preco_referencia(self, produto_id: str, loja: str):
        row = self.conexao.execute(
            "SELECT preco_referencia FROM public.referencias_precos WHERE loja=%s AND produto_id=%s",
            (loja, produto_id),
        ).fetchone()
        return Preco(row['preco_referencia']) if row else None

    def remover(self, produto_id: str, loja: str) -> None:
        self.conexao.execute(
            "DELETE FROM public.ofertas WHERE loja=%s AND produto_id=%s",
            (loja, produto_id),
        )

    def salvar(self, oferta: Oferta) -> None:
        codigo = oferta.cupom.codigo if oferta.cupom else None
        percentual = oferta.cupom.desconto_percentual if oferta.cupom else None
        preco_de = oferta.preco_de.valor if oferta.preco_de else None
        with self.conexao.transaction():
            # O preço de referência é gravado uma vez, mesmo que a oferta saia e volte.
            self.conexao.execute(
                """INSERT INTO public.referencias_precos (loja,produto_id,preco_referencia)
                VALUES (%s,%s,%s) ON CONFLICT (loja,produto_id) DO NOTHING""",
                (oferta.loja, oferta.produto_id, oferta.preco_referencia.valor),
            )
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

    def historico_recente(self, produto_id: str, loja: str) -> HistoricoRecente:
        # Usa o índice (loja, produto_id, coletado_em). Roda dentro da transação
        # do produto, antes de salvar: a coleta atual ainda não está no histórico.
        row = self.conexao.execute(
            """SELECT min(preco_final) FILTER (
                          WHERE coletado_em >= clock_timestamp() - interval '30 days') AS menor,
                      extract(epoch FROM clock_timestamp() - min(coletado_em)) / 86400 AS dias
               FROM public.historico_precos WHERE loja=%s AND produto_id=%s""",
            (loja, produto_id),
        ).fetchone()
        if row is None or row['dias'] is None:
            return HistoricoRecente()
        return HistoricoRecente(
            menor_preco_30_dias=Preco(row['menor']) if row['menor'] is not None else None,
            dias_acompanhado=float(row['dias']),
        )


class FonteDeProdutosPostgres(FonteDeProdutosMonitorados):
    def __init__(self, conexao):
        self.conexao = conexao

    def listar(self) -> list[ProdutoMonitorado]:
        rows = self.conexao.execute(
            "SELECT loja,url,tipo,paginas FROM public.produtos_monitorados WHERE ativo ORDER BY id"
        ).fetchall()
        return [ProdutoMonitorado(**row) for row in rows]
