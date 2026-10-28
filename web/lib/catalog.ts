import { readJsonProducts } from './catalog/json-source';
import { readPostgresProducts } from './catalog/postgres-source';
import type { Catalog, Product } from './catalog/types';

export type { Catalog, Product, Observation } from './catalog/types';

// Strategy: as duas fontes seguem o mesmo contrato de leitura.
const productSources: Record<Catalog['source'], () => Promise<Product[]>> = {
  json: readJsonProducts,
  postgres: readPostgresProducts,
};

// Facade: a página só precisa chamar esta função, sem conhecer as fontes.
export async function getCatalog(): Promise<Catalog> {
  const source = process.env.DATABASE_URL ? 'postgres' : 'json';
  try {
    const products = await productSources[source]();
    return { products, source, error: false };
  } catch {
    // Nunca envie credenciais ou mensagens internas do Python ao navegador.
    return { products: [], source, error: true };
  }
}
