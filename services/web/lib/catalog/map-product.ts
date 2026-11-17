import type { Product } from './types';

// Converte a URL do scraper para o formato usado pela interface.
export type Row = Record<string, string>;
export function mapProduct(row: Row): Product {
  const url = new URL(row.url);
  if (!['https:', 'http:'].includes(url.protocol) || !row.loja)
    throw new Error('Invalid product');
  const id = url.pathname.match(/\/produto\/([^/]+)/)?.[1] ?? row.url;
  const slug = url.pathname.split('/').filter(Boolean).at(-1);
  return {
    id,
    store: row.loja,
    url: url.href,
    label:
      slug && slug !== id
        ? decodeURIComponent(slug).replaceAll('-', ' ')
        : `Produto ${id}`,
    price: null,
    reference: null,
    updated: null,
    history: [],
  };
}
