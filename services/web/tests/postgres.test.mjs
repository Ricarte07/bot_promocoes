import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';
import { execFileSync } from 'node:child_process';

registerHooks({
  resolve(specifier, context, nextResolve) {
    // Só o código do projeto usa imports sem extensão para arquivos .ts; os pacotes em node_modules ficam como estão.
    if (specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier) && !context.parentURL?.includes('/node_modules/')) return nextResolve(`${specifier}.ts`, context);
    return nextResolve(specifier, context);
  },
});
const { closeAtLastVisit, connectionConfig, mapDatabaseProducts, readPostgresProducts } = await import('../lib/catalog/postgres-source.ts');
const { isPromotion } = await import('../lib/products/selectors.ts');

test('ofertas descobertas em categorias usam nome e ID coletados, sem depender dos endereços monitorados', () => {
  const [product] = mapDatabaseProducts({
    offers: [{ loja: 'americanas', produto_id: 'id-real-coletado', nome: 'Nome real',
      url: 'https://www.americanas.com.br/produto-123/p', preco_atual: '100',
      preco_referencia: '150', preco_final: '90', cupom_codigo: 'DEZ',
      cupom_desconto_percentual: '10', atualizada_em: '2026-11-03' }],
    history: [{ loja: 'americanas', produto_id: 'id-real-coletado', preco: '100', coletado_em: '2026-11-03' }],
  });
  assert.equal(product.id, 'id-real-coletado');
  assert.equal(product.label, 'Nome real');
  assert.equal(product.price, 100);
  assert.equal(product.coupon, 'DEZ');
  assert.equal(product.finalPrice, 90);
  assert.equal(product.history.length, 1);
});

test('histórico de cada produto fica só com as observações dele, em ordem', () => {
  const offer = (loja, produto_id) => ({ loja, produto_id, nome: produto_id,
    url: `https://www.kabum.com.br/produto/${produto_id}/x`, preco_atual: '10',
    preco_referencia: '10', preco_final: '10', atualizada_em: '2026-11-18' });
  const point = (loja, produto_id, preco, coletado_em) => ({ loja, produto_id, preco, coletado_em });
  const [kabumA, kabumB, americanasA] = mapDatabaseProducts({
    offers: [offer('kabum', 'a'), offer('kabum', 'b'), offer('americanas', 'a')],
    history: [
      point('kabum', 'a', '10', '2026-11-18T10:00'),
      point('kabum', 'b', '20', '2026-11-18T10:00'),
      point('americanas', 'a', '30', '2026-11-18T10:00'),
      point('kabum', 'a', '9', '2026-11-18T11:00'),
    ],
  });
  assert.deepEqual(kabumA.history.map((p) => p.price), [10, 9]);
  assert.deepEqual(kabumB.history.map((p) => p.price), [20]);
  // Mesmo id em outra loja é outro produto.
  assert.deepEqual(americanasA.history.map((p) => p.price), [30]);
});

test('gráfico vai até a última visita com o preço que continua valendo', () => {
  const [product] = mapDatabaseProducts({
    offers: [{ loja: 'kabum', produto_id: 'p', nome: 'P', url: 'https://www.kabum.com.br/produto/1/x',
      preco_atual: '90', preco_referencia: '100', preco_final: '90',
      atualizada_em: '2026-11-23 17:18:29.730414+00:00' }],
    history: [
      { loja: 'kabum', produto_id: 'p', preco: '100', coletado_em: '2026-11-18 10:00:00+00:00' },
      { loja: 'kabum', produto_id: 'p', preco: '90', coletado_em: '2026-11-20 10:00:00+00:00' },
    ],
  });
  assert.deepEqual(product.history.map((p) => p.price), [100, 90, 90]);
  assert.equal(product.history.at(-1).date, '2026-11-23 17:18:29.730414+00:00');
});

test('sem visita mais nova que a última mudança, o histórico fica como veio', () => {
  const history = [{ price: 10, date: '2026-11-20 10:00:00+00:00' }];
  assert.equal(closeAtLastVisit(history, 10, '2026-11-20 10:00:00+00:00'), history);
  assert.equal(closeAtLastVisit(history, 10, null), history);
  assert.equal(closeAtLastVisit(history, null, '2026-11-23'), history);
  assert.deepEqual(closeAtLastVisit([], 10, '2026-11-23'), []);
});

test('conexão: banco remoto só com SSL, local sem SSL, e o sslmode sai da URL', () => {
  const remoto = connectionConfig('postgresql://u:s%40x@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require');
  assert.deepEqual(remoto.ssl, { rejectUnauthorized: false });
  assert.ok(!remoto.connectionString.includes('sslmode'));
  assert.ok(remoto.connectionString.includes('s%40x'), 'a senha codificada continua codificada');
  assert.equal(remoto.keepAlive, true);
  assert.match(remoto.options, /default_transaction_read_only=on/);
  assert.equal(connectionConfig('postgresql://u:s@127.0.0.1:5432/x').ssl, false);
  assert.throws(() => connectionConfig('postgresql://u:s@db.exemplo.com/x?sslmode=disable'), /SSL/);
});

test('produto sem histórico recebe lista vazia', () => {
  const [product] = mapDatabaseProducts({
    offers: [{ loja: 'kabum', produto_id: 'novo', nome: 'Novo', url: 'https://www.kabum.com.br/produto/1/x',
      preco_atual: '10', preco_referencia: '10', preco_final: '10', atualizada_em: '2026-11-18' }],
    history: [],
  });
  assert.deepEqual(product.history, []);
});

test('web consulta dados gravados pelo coletor em banco descartável',
  { skip: !process.env.TEST_DATABASE_URL }, async () => {
    const python = process.env.SCRAPER_PYTHON || 'python3';
    const run = (script) => execFileSync(python, ['-c', script], { encoding: 'utf8' });
    // Nunca usa DATABASE_URL para criar/remover bancos.
    const setup = `
import os,json
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict,make_conninfo
url=os.environ['TEST_DATABASE_URL']
assert conninfo_to_dict(url)['dbname'].endswith('_test')
name='bot_web_'+uuid4().hex+'_test'
with psycopg.connect(url,autocommit=True) as c:
    c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
# O painel usa o driver pg, que só aceita a conexão no formato de URL.
from urllib.parse import quote
d=conninfo_to_dict(url)
web=f"postgresql://{quote(d.get('user',''),safe='')}:{quote(d.get('password',''),safe='')}@{d.get('host','localhost')}:{d.get('port','5432')}/{name}"
print(json.dumps(dict(name=name,url=make_conninfo(url,dbname=name),web=web)))
`;
    const database = JSON.parse(run(setup));
    const original = process.env.DATABASE_URL;
    const originalPanel = process.env.PANEL_DATABASE_URL;
    try {
      // O Python do scraper grava por DATABASE_URL; o painel lê por PANEL_DATABASE_URL,
      // no formato de URL que o driver pg aceita. Os dois apontam para o banco descartável.
      process.env.DATABASE_URL = database.url;
      process.env.PANEL_DATABASE_URL = database.web;
      run(`
import os,sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path('../scraper').resolve()))
from infrastructure.persistencia.postgres import conectar,OfertaRepositorioPostgres
from infrastructure.mensageria.postgres import PublicadorPostgres
from application.processar_coleta import ProcessarColeta
from application.portas import PrecoColetado
from domain.preco import Preco
from domain.cupom import Cupom
class Coletor:
    def __init__(self,valor): self.valor=valor
    def coletar(self):
        return [PrecoColetado('999','kabum',Preco(Decimal(self.valor)),'Descoberto na categoria','https://www.kabum.com.br/produto/999/exemplo',Cupom('CODIGO'))]
with conectar(os.environ['DATABASE_URL']) as c:
    c.execute(Path('../../sql/schema.sql').read_text())
    # Quatro coletas: o preço só muda uma vez.
    for valor in ('100','100','90','90'):
        ProcessarColeta(Coletor(valor),OfertaRepositorioPostgres(c),PublicadorPostgres(c)).executar()
`);
      const products = await readPostgresProducts();
      assert.equal(products.length, 1);
      assert.equal(products[0].label, 'Descoberto na categoria');
      assert.equal(products[0].price, 90);
      assert.equal(products[0].coupon, 'CODIGO');
      assert.equal(products[0].couponDiscount, null);
      // Primeira coleta, a mudança para 90 e a coleta mais recente; a repetição de 100 sai.
      assert.deepEqual(products[0].history.map((p) => p.price), [100, 90, 90]);
      // 10% abaixo da referência: o bot não chama de promoção, e o painel também não.
      assert.equal(products[0].onSale, false);

      // Cai para 80 (20%): o bot marca em_promocao, e o painel conta o mesmo que o banco.
      run(`
import os,sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path('../scraper').resolve()))
from infrastructure.persistencia.postgres import conectar,OfertaRepositorioPostgres
from infrastructure.mensageria.postgres import PublicadorPostgres
from application.processar_coleta import ProcessarColeta
from application.portas import PrecoColetado
from domain.preco import Preco
class Coletor:
    def coletar(self):
        return [PrecoColetado('999','kabum',Preco(Decimal('80')),'Descoberto na categoria','https://www.kabum.com.br/produto/999/exemplo')]
with conectar(os.environ['DATABASE_URL']) as c:
    ProcessarColeta(Coletor(),OfertaRepositorioPostgres(c),PublicadorPostgres(c)).executar()
`);
      const depois = await readPostgresProducts();
      const agora = Date.now();
      const noPainel = depois.filter((p) => isPromotion(p, agora)).length;
      const noBanco = Number(run(`
import os,psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as c:
    print(c.execute("SELECT count(*) FROM public.ofertas WHERE em_promocao AND atualizada_em > now() - interval '24 hours'").fetchone()[0])
`).trim());
      assert.equal(depois[0].onSale, true);
      // A origem e o desconto aprovados pelo bot chegam ao painel.
      assert.equal(depois[0].discountOrigin, 'referencia');
      assert.equal(depois[0].botDiscount, 20);
      assert.equal(noPainel, 1);
      assert.equal(noPainel, noBanco);
    } finally {
      if (original === undefined) delete process.env.DATABASE_URL;
      else process.env.DATABASE_URL = original;
      if (originalPanel === undefined) delete process.env.PANEL_DATABASE_URL;
      else process.env.PANEL_DATABASE_URL = originalPanel;
      run(`
import os,psycopg
from psycopg import sql
with psycopg.connect(os.environ['TEST_DATABASE_URL'],autocommit=True) as c:
    c.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier('${database.name}')))
`);
    }
  });
