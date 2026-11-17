import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier)) return nextResolve(`${specifier}.ts`, context);
    return nextResolve(specifier, context);
  },
});
const { calculateDiscount, discountBase, filterProducts, EMPTY_FILTERS } = await import('../lib/products/selectors.ts');
const { mapDatabaseProducts } = await import('../lib/catalog/postgres-source.ts');

test('desconto usa preço de e cupom conhecidos, com fallback para referência', () => {
  const [product] = mapDatabaseProducts({ offers: [{ loja: 'kabum', produto_id: '1', nome: 'Produto', url: 'https://www.kabum.com.br/produto/1', preco_atual: '2400', preco_referencia: '2400', preco_de: '3000', preco_final: '2160', cupom_codigo: 'DEZ', cupom_desconto_percentual: '10', atualizada_em: '2026-11-03' }], history: [] });
  assert.equal(discountBase(product), 3000);
  assert.ok(Math.abs(calculateDiscount(product) - 28) < 0.0001);
  assert.equal(filterProducts([product], { ...EMPTY_FILTERS, discount: '25' }).length, 1);
  assert.equal(calculateDiscount({ ...product, listPrice: null, finalPrice: 2400 }), 0);
  assert.ok(Math.abs(calculateDiscount({ ...product, reference: 4000, listPrice: 3000, finalPrice: 2400 }) - 40) < 0.0001);
  assert.equal(calculateDiscount({ ...product, reference: null, listPrice: null }), null);
});
