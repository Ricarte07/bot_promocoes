// Run from web with Node 24: node --experimental-strip-types --test tests/catalog.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { registerHooks } from 'node:module';

registerHooks({
  resolve(specifier, context, nextResolve) {
    // Só o código do projeto usa imports sem extensão para arquivos .ts; os pacotes em node_modules ficam como estão.
    if (specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier) && !context.parentURL?.includes('/node_modules/')) return nextResolve(`${specifier}.ts`, context);
    return nextResolve(specifier, context);
  },
});
const { getCatalog } = await import('../lib/catalog.ts');

test('catalog reads real URLs and handles missing or invalid data without fabrication', async () => {
  const original = {
    DATABASE_URL: process.env.DATABASE_URL,
    CATALOG_SOURCE: process.env.CATALOG_SOURCE,
    PRODUCTS_FILE: process.env.PRODUCTS_FILE,
    SCRAPER_PYTHON: process.env.SCRAPER_PYTHON,
    PANEL_DATABASE_URL: process.env.PANEL_DATABASE_URL,
  };
  const dir = await mkdtemp(path.join(tmpdir(), 'radar-test-'));
  try {
    delete process.env.DATABASE_URL;
    process.env.CATALOG_SOURCE = 'json';
    process.env.PRODUCTS_FILE = path.resolve(
      '../scraper/produtos.json',
    );
    const catalog = await getCatalog();
    assert.equal(catalog.error, false);
    assert.ok(catalog.products.length > 0);
    assert.ok(
      catalog.products.every(
        (p) =>
          p.price === null && p.reference === null && p.history.length === 0,
      ),
    );
    process.env.PRODUCTS_FILE = path.join(dir, 'products.json');
    for (const [contents, error] of [
      ['[]', false],
      ['[{"loja":"kabum","listagem":"https://www.kabum.com.br/hardware"}]', false],
      ['invalid', true],
      ['{}', true],
      ['[{"loja":"x","url":"javascript:alert(1)"}]', true],
    ]) {
      await writeFile(process.env.PRODUCTS_FILE, contents);
      const result = await getCatalog();
      assert.equal(result.error, error);
      assert.deepEqual(result.products, []);
    }
    process.env.PRODUCTS_FILE = path.join(dir, 'missing.json');
    assert.equal((await getCatalog()).error, true);
    process.env.CATALOG_SOURCE = 'postgres';
    process.env.DATABASE_URL = 'postgresql://secret:secret@unavailable/test';
    // Vazio (e não apagado): senão o painel leria o usuário só-leitura do .env da raiz.
    process.env.PANEL_DATABASE_URL = '';
    const failure = await getCatalog();
    assert.equal(failure.source, 'postgres');
    assert.equal(failure.error, true);
    assert.ok(!JSON.stringify(failure).includes('secret'));
  } finally {
    for (const [key, value] of Object.entries(original)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    await rm(dir, { recursive: true, force: true });
  }
});
