import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';
import { execFileSync } from 'node:child_process';

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier)) return nextResolve(`${specifier}.ts`, context);
    return nextResolve(specifier, context);
  },
});
const { mapDatabaseProducts, readPostgresProducts } = await import('../lib/catalog/postgres-source.ts');

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
print(json.dumps(dict(name=name,url=make_conninfo(url,dbname=name))))
`;
    const database = JSON.parse(run(setup));
    const original = process.env.DATABASE_URL;
    try {
      process.env.DATABASE_URL = database.url;
      run(`
import os,sys
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path('../services/scraper').resolve()))
from infrastructure.persistencia.postgres import conectar,OfertaRepositorioPostgres
from infrastructure.mensageria.postgres import PublicadorPostgres
from application.processar_coleta import ProcessarColeta
from application.portas import PrecoColetado
from domain.preco import Preco
from domain.cupom import Cupom
class Coletor:
    def coletar(self):
        return [PrecoColetado('999','kabum',Preco(Decimal('100')),'Descoberto na categoria','https://www.kabum.com.br/produto/999/exemplo',Cupom('CODIGO'))]
with conectar(os.environ['DATABASE_URL']) as c:
    c.execute(Path('../sql/schema.sql').read_text())
    ProcessarColeta(Coletor(),OfertaRepositorioPostgres(c),PublicadorPostgres(c)).executar()
`);
      const products = await readPostgresProducts();
      assert.equal(products.length, 1);
      assert.equal(products[0].label, 'Descoberto na categoria');
      assert.equal(products[0].price, 100);
      assert.equal(products[0].coupon, 'CODIGO');
      assert.equal(products[0].couponDiscount, null);
      assert.equal(products[0].history.length, 1);
    } finally {
      if (original === undefined) delete process.env.DATABASE_URL;
      else process.env.DATABASE_URL = original;
      run(`
import os,psycopg
from psycopg import sql
with psycopg.connect(os.environ['TEST_DATABASE_URL'],autocommit=True) as c:
    c.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier('${database.name}')))
`);
    }
  });
