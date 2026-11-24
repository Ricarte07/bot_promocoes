import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier)) return nextResolve(`${specifier}.ts`, context);
    return nextResolve(specifier, context);
  },
});
const { EMPTY_FILTERS, filterProducts, hoursSinceSeen, isPromotion, isStale, sortByLowestPrice } =
  await import('../lib/products/selectors.ts');
const { formatSeenAgo } = await import('../lib/products/format.ts');
const { mapDatabaseProducts } = await import('../lib/catalog/postgres-source.ts');

const AGORA = Date.parse('2026-11-24T18:00:00Z');
const horasAtras = (h) => new Date(AGORA - h * 3600_000).toISOString();

function oferta(campos = {}) {
  return {
    loja: 'kabum', produto_id: '1', nome: 'Placa', url: 'https://www.kabum.com.br/produto/1/placa',
    preco_atual: '100', preco_referencia: '150', preco_final: '100', em_promocao: true,
    atualizada_em: horasAtras(2), ...campos,
  };
}
const produto = (campos) => mapDatabaseProducts({ offers: [oferta(campos)], history: [] })[0];

test('o painel mostra o veredito do bot, gravado em em_promocao', () => {
  assert.equal(produto({ em_promocao: true }).onSale, true);
  assert.equal(produto({ em_promocao: false }).onSale, false);
  // Mesmo com 33% de diferença para a referência, sem o veredito não é promoção.
  assert.equal(isPromotion(produto({ em_promocao: false }), AGORA), false);
});

test('promoção só vale se o bot viu o produto nas últimas 24 h', () => {
  assert.equal(isPromotion(produto({ atualizada_em: horasAtras(2) }), AGORA), true);
  assert.equal(isPromotion(produto({ atualizada_em: horasAtras(30) }), AGORA), false);
  assert.equal(isStale(produto({ atualizada_em: horasAtras(30) }), AGORA), true);
  assert.equal(isStale(produto({ atualizada_em: horasAtras(23) }), AGORA), false);
  // Sem data, não dá para afirmar que o preço é atual.
  assert.equal(isPromotion({ ...produto(), updated: null }, AGORA), false);
  assert.equal(hoursSinceSeen({ ...produto(), updated: null }, AGORA), null);
});

test('"visto há" em minutos, horas e dias', () => {
  assert.equal(formatSeenAgo(0.2), 'há 12 min');
  assert.equal(formatSeenAgo(0), 'há 1 min');
  assert.equal(formatSeenAgo(3.7), 'há 3 h');
  assert.equal(formatSeenAgo(47), 'há 47 h');
  assert.equal(formatSeenAgo(50), 'há 2 dias');
});

test('filtro "só promoções do bot" e preço do filtro igual ao do desconto', () => {
  const emPromocao = produto({ produto_id: '1' });
  const semPromocao = produto({ produto_id: '2', em_promocao: false });
  const vencida = produto({ produto_id: '3', atualizada_em: horasAtras(48) });
  const lista = [emPromocao, semPromocao, vencida];
  assert.deepEqual(
    filterProducts(lista, { ...EMPTY_FILTERS, show: 'promocoes' }, AGORA).map((p) => p.id), ['1']);

  // Preço 100, com cupom 90: o filtro usa o que o comprador paga.
  const comCupom = produto({ preco_final: '90' });
  assert.equal(filterProducts([comCupom], { ...EMPTY_FILTERS, maximum: '95' }, AGORA).length, 1);
  assert.equal(filterProducts([comCupom], { ...EMPTY_FILTERS, minimum: '95' }, AGORA).length, 0);
  assert.deepEqual(sortByLowestPrice([produto({ produto_id: 'a', preco_final: '95' }), comCupom]).map((p) => p.finalPrice), [90, 95]);
});

test('origem e desconto aprovados pelo bot chegam ao painel e têm prioridade', async () => {
  const { promotionDiscount, ORIGIN_LABELS } = await import('../lib/products/selectors.ts');
  const p = produto({ base_desconto: 'menor_30_dias', desconto_percentual: '12.50', preco_de: '300' });
  assert.equal(p.discountOrigin, 'menor_30_dias');
  assert.equal(p.botDiscount, 12.5);
  // O "de" de 300 daria 66,7% pela conta do painel; vale o que o bot aprovou.
  assert.equal(promotionDiscount(p), 12.5);
  assert.equal(ORIGIN_LABELS[p.discountOrigin], 'menor preço em 30 dias');
  // Origem desconhecida ou ausente vira null, sem quebrar a tela.
  assert.equal(produto({ base_desconto: 'outra' }).discountOrigin, null);
  assert.equal(produto({ base_desconto: null }).botDiscount, null);
});

test('filtro por origem mostra só promoções válidas daquela origem', () => {
  const queda = produto({ produto_id: '1', base_desconto: 'referencia' });
  const deLoja = produto({ produto_id: '2', base_desconto: 'preco_de_loja' });
  const deLojaVencida = produto({ produto_id: '3', base_desconto: 'preco_de_loja', atualizada_em: horasAtras(30) });
  const lista = [queda, deLoja, deLojaVencida];
  assert.deepEqual(filterProducts(lista, { ...EMPTY_FILTERS, show: 'preco_de_loja' }, AGORA).map((x) => x.id), ['2']);
  assert.deepEqual(filterProducts(lista, { ...EMPTY_FILTERS, show: 'referencia' }, AGORA).map((x) => x.id), ['1']);
});
