import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerHooks } from 'node:module';

registerHooks({
  resolve(specifier, context, nextResolve) {
    // Só o código do projeto usa imports sem extensão para arquivos .ts; os pacotes em node_modules ficam como estão.
    if (specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier) && !context.parentURL?.includes('/node_modules/')) return nextResolve(`${specifier}.ts`, context);
    return nextResolve(specifier, context);
  },
});
const { stepPath, lowestLineY, CHART } = await import('../lib/products/chart.ts');
const { matchesSearch, sortProducts } = await import('../lib/products/selectors.ts');
const { formatTime } = await import('../lib/products/format.ts');

const ponto = (price, date) => ({ price, date });

test('gráfico em degraus: anda na horizontal até a mudança e só então sobe ou desce', () => {
  const caminho = stepPath([
    ponto(3402.99, '2026-11-18T00:00:00Z'),
    ponto(3499.99, '2026-11-23T00:00:00Z'),
    ponto(3499.99, '2026-11-28T00:00:00Z'),
  ]);
  // Começa embaixo (menor preço), vai reto até 23/11 (metade do eixo) e sobe para o topo.
  assert.equal(caminho, `M0 ${CHART.height - CHART.padding} H300 V${CHART.padding} H600 V${CHART.padding}`);
  assert.equal(lowestLineY([ponto(1, '2026-11-18'), ponto(2, '2026-11-19')]), CHART.height - CHART.padding);
});

test('preço constante fica no meio, e um ponto só não desenha linha', () => {
  assert.equal(stepPath([ponto(10, '2026-11-18'), ponto(10, '2026-11-19')]), `M0 ${CHART.height / 2} H600 V${CHART.height / 2}`);
  assert.equal(stepPath([ponto(10, '2026-11-18')]), '');
});

test('ordenação: maior desconto primeiro, e produto sem o dado vai para o fim', () => {
  const p = (id, campos) => ({ id, store: 'kabum', url: 'https://x', label: id, price: 100, finalPrice: 100,
    reference: 100, listPrice: null, updated: null, history: [], ...campos });
  const lista = [p('sem-base', { reference: null }), p('10', { reference: 111.12 }), p('40', { reference: 166.67 })];
  assert.deepEqual(sortProducts(lista, 'desconto', 0).map((x) => x.id), ['40', '10', 'sem-base']);
  assert.deepEqual(sortProducts(lista, 'nome', 0).map((x) => x.id), ['10', '40', 'sem-base']);
  const precos = [p('caro', { finalPrice: 300 }), p('sem', { finalPrice: null, price: null }), p('barato', { finalPrice: 50 })];
  assert.deepEqual(sortProducts(precos, 'preco', 0).map((x) => x.id), ['barato', 'caro', 'sem']);
  // Não altera a lista original.
  assert.equal(lista[0].id, 'sem-base');
});

test('hora dos dados sai no horário de Brasília', () => {
  // 18:30 em UTC é 15:30 em Brasília.
  assert.equal(formatTime('2026-11-25T18:30:00Z'), '15:30');
  assert.equal(formatTime('2026-11-25T03:05:00Z'), '00:05');
});

test('busca ignora acentos, maiúsculas, hífen e a ordem das palavras', () => {
  const nome = 'Placa Mãe ASUS X870 MAX GAMING WIFI7, AMD, AM5, ATX, DDR5';
  for (const busca of ['Placa Mae', 'placa mãe', 'PLACA-MAE', 'x870 asus', 'asus placa max', 'ddr5', '  ', ''])
    assert.ok(matchesSearch(nome, busca), `deveria achar com "${busca}"`);
  assert.ok(matchesSearch('Placa-Mãe ASUS TUF GAMING X870-PLUS', 'placa mae x870 plus'));
  // Todas as palavras precisam estar no nome.
  assert.ok(!matchesSearch(nome, 'placa mae gigabyte'));
  assert.ok(!matchesSearch(nome, 'rtx'));
});
