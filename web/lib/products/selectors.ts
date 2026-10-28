import type { Product } from '../catalog/types';

// Campos de formulário usam texto: string vazia significa "sem filtro".
export type ProductFilters = {
  search: string;
  store: string;
  minimum: string;
  maximum: string;
  discount: string;
};

export const EMPTY_FILTERS: ProductFilters = {
  search: '',
  store: '',
  minimum: '',
  maximum: '',
  discount: '',
};

export function calculateDiscount(product: Product): number | null {
  if (
    product.price === null ||
    product.reference === null ||
    product.reference <= 0
  ) {
    return null;
  }
  return Math.max(0, (1 - product.price / product.reference) * 100);
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
): Product[] {
  if (hasInvalidPriceRange(filters)) return [];

  return products.filter((product) => {
    if (filters.store && product.store !== filters.store) return false;
    if (!product.label.toLowerCase().includes(filters.search.toLowerCase()))
      return false;

    // Preço ausente não pode passar por um filtro que exige preço.
    if (
      filters.minimum !== '' &&
      (product.price === null || product.price < Number(filters.minimum))
    )
      return false;
    if (
      filters.maximum !== '' &&
      (product.price === null || product.price > Number(filters.maximum))
    )
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
    .filter((product) => product.price !== null)
    .sort((first, second) => first.price! - second.price!);
}
