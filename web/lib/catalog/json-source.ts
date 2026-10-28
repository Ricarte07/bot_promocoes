import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { mapProduct } from './map-product';
import type { Product } from './types';

export async function readJsonProducts(): Promise<Product[]> {
  const filePath =
    process.env.PRODUCTS_FILE ||
    path.resolve(process.cwd(), '../services/scraper/produtos.json');
  const contents = await readFile(filePath, 'utf8');
  const rows = JSON.parse(contents);

  if (!Array.isArray(rows)) {
    throw new Error('O catálogo precisa ser uma lista de produtos.');
  }
  return rows.map(mapProduct);
}
