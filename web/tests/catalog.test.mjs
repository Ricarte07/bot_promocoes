// Run from web with Node 24: node --experimental-strip-types --test tests/catalog.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { registerHooks } from 'node:module';

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier)) return nextResolve(`${specifier}.ts`, context);
    return nextResolve(specifier, context);
  },
});
const { getCatalog } = await import('../lib/catalog.ts');

test('catalog reads real URLs and handles missing or invalid data without fabrication', async () => {
  const original = {
    DATABASE_URL: process.env.DATABASE_URL,
    PRODUCTS_FILE: process.env.PRODUCTS_FILE,
    SCRAPER_PYTHON: process.env.SCRAPER_PYTHON,
  };
  const dir = await mkdtemp(path.join(tmpdir(), 'radar-test-'));
  try {
    delete process.env.DATABASE_URL;
    process.env.PRODUCTS_FILE = path.resolve(
      '../services/scraper/produtos.json',
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
    process.env.DATABASE_URL = 'postgresql://secret:secret@unavailable/test';
    process.env.SCRAPER_PYTHON = path.join(dir, 'missing-python');
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
