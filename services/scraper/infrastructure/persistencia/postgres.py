"""Adaptadores PostgreSQL. A conexão fica apenas nos serviços, nunca no navegador."""

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict

from application.portas import FonteDeProdutosMonitorados, ProdutoMonitorado
from domain.cupom import Cupom
from domain.oferta import EstadoOferta, Oferta
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
        # Reidratar sem registrar_preco: carregar estado não é uma nova coleta/evento.
        return Oferta.restaurar(EstadoOferta(
            produto_id=produto_id,
            loja=loja,
            nome=row['nome'],
            url=row['url'],
            preco_referencia=Preco(row['preco_referencia']),
            preco_atual=Preco(row['preco_atual']),
            preco_final=Preco(row['preco_final']),
            preco_de=Preco(row['preco_de']) if row['preco_de'] is not None else None,
            cupom=(Cupom(row['cupom_codigo'], row['cupom_desconto_percentual'])
                   if row['cupom_codigo'] else None),
            em_promocao=row['em_promocao'],
            base_desconto=row['base_desconto'],
            desconto_percentual=row['desconto_percentual'],
        ))

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
        e = oferta.estado()
        codigo = e.cupom.codigo if e.cupom else None
        percentual = e.cupom.desconto_percentual if e.cupom else None
        preco_de = e.preco_de.valor if e.preco_de else None
        with self.conexao.transaction():
            # O preço de referência é gravado uma vez, mesmo que a oferta saia e volte.
            self.conexao.execute(
                """INSERT INTO public.referencias_precos (loja,produto_id,preco_referencia)
                VALUES (%s,%s,%s) ON CONFLICT (loja,produto_id) DO NOTHING""",
                (e.loja, e.produto_id, e.preco_referencia.valor),
            )
            self.conexao.execute(
                """INSERT INTO public.ofertas
                (loja,produto_id,nome,url,preco_referencia,preco_atual,preco_de,
                 preco_final,cupom_codigo,cupom_desconto_percentual,em_promocao,
                 base_desconto,desconto_percentual)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (loja,produto_id) DO UPDATE SET
                nome=EXCLUDED.nome,url=EXCLUDED.url,preco_atual=EXCLUDED.preco_atual,
                preco_de=EXCLUDED.preco_de,preco_final=EXCLUDED.preco_final,
                cupom_codigo=EXCLUDED.cupom_codigo,
                cupom_desconto_percentual=EXCLUDED.cupom_desconto_percentual,
                em_promocao=EXCLUDED.em_promocao,base_desconto=EXCLUDED.base_desconto,
                desconto_percentual=EXCLUDED.desconto_percentual,atualizada_em=clock_timestamp()""",
                (e.loja, e.produto_id, e.nome, e.url,
                 e.preco_referencia.valor, e.preco_atual.valor, preco_de,
                 e.preco_final.valor, codigo, percentual, e.em_promocao,
                 e.base_desconto, e.desconto_percentual),
            )
            # O histórico guarda mudanças, não coletas: uma linha nova só quando
            # preço, "de", preço final ou cupom diferem da última linha do produto.
            # Quando o produto foi visto pela última vez fica em ofertas.atualizada_em.
            self.conexao.execute(
                """INSERT INTO public.historico_precos
                (loja,produto_id,preco,preco_de,preco_final,cupom_codigo,cupom_desconto_percentual)
                SELECT %(loja)s, %(produto_id)s, %(preco)s::numeric, %(preco_de)s::numeric,
                       %(preco_final)s::numeric, %(codigo)s::text, %(percentual)s::numeric
                WHERE NOT EXISTS (
                    SELECT 1 FROM (
                        SELECT preco, preco_de, preco_final, cupom_codigo, cupom_desconto_percentual
                        FROM public.historico_precos
                        WHERE loja=%(loja)s AND produto_id=%(produto_id)s
                        ORDER BY coletado_em DESC, id DESC LIMIT 1
                    ) ultima
                    WHERE ultima.preco = %(preco)s::numeric
                      AND ultima.preco_de IS NOT DISTINCT FROM %(preco_de)s::numeric
                      AND ultima.preco_final = %(preco_final)s::numeric
                      AND ultima.cupom_codigo IS NOT DISTINCT FROM %(codigo)s::text
                      AND ultima.cupom_desconto_percentual IS NOT DISTINCT FROM %(percentual)s::numeric
                )""",
                {"loja": e.loja, "produto_id": e.produto_id,
                 "preco": e.preco_atual.valor, "preco_de": preco_de,
                 "preco_final": e.preco_final.valor, "codigo": codigo,
                 "percentual": percentual},
            )

    def historico_recente(self, produto_id: str, loja: str) -> HistoricoRecente:
        # Usa o índice (loja, produto_id, coletado_em). Roda dentro da transação
        # do produto, antes de salvar: a coleta atual ainda não está no histórico.
        #
        # Como o histórico só guarda mudanças, o preço que valia no começo da
        # janela de 30 dias está na última linha anterior a ela: um preço que não
        # muda há 40 dias continua sendo "o menor dos últimos 30 dias".
        row = self.conexao.execute(
            """SELECT least(
                   (SELECT min(preco_final) FROM public.historico_precos
                     WHERE loja=%(loja)s AND produto_id=%(produto_id)s
                       AND coletado_em >= clock_timestamp() - interval '30 days'),
                   (SELECT preco_final FROM public.historico_precos
                     WHERE loja=%(loja)s AND produto_id=%(produto_id)s
                       AND coletado_em < clock_timestamp() - interval '30 days'
                     ORDER BY coletado_em DESC, id DESC LIMIT 1)
               ) AS menor,
               (SELECT extract(epoch FROM clock_timestamp() - min(coletado_em)) / 86400
                  FROM public.historico_precos
                 WHERE loja=%(loja)s AND produto_id=%(produto_id)s) AS dias""",
            {"loja": loja, "produto_id": produto_id},
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
