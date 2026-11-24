import type { DiscountOrigin, Product } from '../catalog/types';

// Campos de formulário usam texto: string vazia significa "sem filtro".
export type ProductFilters = {
  search: string;
  store: string;
  minimum: string;
  maximum: string;
  discount: string;
  // 'promocoes' mostra só o que o bot considera promoção agora.
  show: string;
};

export const EMPTY_FILTERS: ProductFilters = {
  search: '',
  store: '',
  minimum: '',
  maximum: '',
  discount: '',
  show: '',
};

// Produto não visto pelo scraper nesse tempo deixa de valer como preço atual.
export const FRESH_HOURS = 24;
const HOUR = 60 * 60 * 1000;

// Horas desde que o scraper viu o produto; null quando a fonte não informa.
export function hoursSinceSeen(product: Product, now: number): number | null {
  if (!product.updated) return null;
  const seen = Date.parse(product.updated);
  if (Number.isNaN(seen)) return null;
  return Math.max(0, (now - seen) / HOUR);
}

export function isStale(product: Product, now: number): boolean {
  const hours = hoursSinceSeen(product, now);
  return hours !== null && hours > FRESH_HOURS;
}

// Promoção é o que o bot decidiu (as regras de 15%, 30 dias e 7 dias ficam no
// scraper), desde que o produto tenha sido visto há pouco: um veredito antigo
// não garante que o preço ainda está lá.
export function isPromotion(product: Product, now: number): boolean {
  return product.onSale === true && !isStale(product, now) && hoursSinceSeen(product, now) !== null;
}

// Como cada origem aparece na tela. A do "de" da loja diz com todas as letras que o
// bot ainda não conferiu o preço riscado (menos de 7 dias de histórico).
export const ORIGIN_LABELS: Record<DiscountOrigin, string> = {
  referencia: 'queda vista pelo bot',
  menor_30_dias: 'menor preço em 30 dias',
  preco_de_loja: '"de" da loja, não conferido',
};

// Valores do filtro "Mostrar" que escolhem uma origem específica.
export const ORIGIN_FILTERS: DiscountOrigin[] = ['referencia', 'menor_30_dias', 'preco_de_loja'];

// O desconto que o bot aprovou; antes da primeira rodada com a origem gravada,
// cai para o cálculo do painel sobre a maior base.
export function promotionDiscount(product: Product): number | null {
  return product.botDiscount ?? calculateDiscount(product);
}

// O que o comprador paga: com o cupom, quando a loja diz quanto ele desconta.
export function effectivePrice(product: Product): number | null {
  return product.finalPrice ?? product.price;
}

// Usa a mesma base do coletor: a que produz o maior desconto sobre o preço final.
// Serve para mostrar o tamanho do desconto; quem decide se é promoção é o bot.
export function discountBase(product: Product): number | null {
  const bases = [product.reference, product.listPrice].filter(
    (value): value is number => value != null && value > 0,
  );
  return bases.length ? Math.max(...bases) : null;
}

export function calculateDiscount(product: Product): number | null {
  const base = discountBase(product);
  const price = effectivePrice(product);
  if (price == null || base === null) return null;
  return Math.max(0, (1 - price / base) * 100);
}

export function hasInvalidPriceRange(filters: ProductFilters): boolean {
  return (
    filters.minimum !== '' &&
    filters.maximum !== '' &&
    Number(filters.minimum) > Number(filters.maximum)
  );
}

export function filterProducts(
  products: Product[],
  filters: ProductFilters,
  now: number = Date.now(),
): Product[] {
  if (hasInvalidPriceRange(filters)) return [];

  return products.filter((product) => {
    if (filters.show === 'promocoes' && !isPromotion(product, now)) return false;
    if (ORIGIN_FILTERS.includes(filters.show as DiscountOrigin) &&
        (!isPromotion(product, now) || product.discountOrigin !== filters.show)) return false;
    if (filters.store && product.store !== filters.store) return false;
    if (!product.label.toLowerCase().includes(filters.search.toLowerCase()))
      return false;

    // Preço ausente não pode passar por um filtro que exige preço. O filtro usa
    // o mesmo preço do desconto: o que o comprador paga.
    const price = effectivePrice(product);
    if (filters.minimum !== '' && (price === null || price < Number(filters.minimum)))
      return false;
    if (filters.maximum !== '' && (price === null || price > Number(filters.maximum)))
      return false;

    const discount = calculateDiscount(product);
    if (
      filters.discount !== '' &&
      (discount === null || discount < Number(filters.discount))
    )
      return false;

    return true;
  });
}

export function sortByLowestPrice(products: Product[]): Product[] {
  // filter cria uma nova lista; sort não altera o catálogo original.
  return products
    .filter((product) => effectivePrice(product) !== null)
    .sort((first, second) => effectivePrice(first)! - effectivePrice(second)!);
}

export type SortOrder = 'desconto' | 'preco' | 'visto' | 'nome';

export const SORT_LABELS: Record<SortOrder, string> = {
  desconto: 'Maior desconto',
  preco: 'Menor preço',
  visto: 'Visto mais recentemente',
  nome: 'Nome (A–Z)',
};

// Produto sem o dado da ordenação vai para o fim, em vez de ser escondido.
export function sortProducts(products: Product[], order: SortOrder, now: number): Product[] {
  const value = (product: Product): number | string | null => {
    switch (order) {
      case 'desconto': return isPromotion(product, now) ? promotionDiscount(product) : calculateDiscount(product);
      case 'preco': return effectivePrice(product);
      case 'visto': return hoursSinceSeen(product, now);
      case 'nome': return product.label.toLocaleLowerCase('pt-BR');
    }
  };
  const direction = order === 'desconto' ? -1 : 1;
  return [...products].sort((first, second) => {
    const a = value(first);
    const b = value(second);
    if (a === null || b === null) return a === b ? 0 : a === null ? 1 : -1;
    if (typeof a === 'string' && typeof b === 'string') return a.localeCompare(b, 'pt-BR') * direction;
    return ((a as number) - (b as number)) * direction;
  });
}
