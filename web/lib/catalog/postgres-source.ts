import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mapProduct } from './map-product';
import type { Row } from './map-product';
import type { Product } from './types';

// Reutiliza psycopg do scraper, somente para leitura. Não inicia uma coleta.
const query = `
import os,json,psycopg
from psycopg.rows import dict_row
with psycopg.connect(os.environ['DATABASE_URL'],row_factory=dict_row,connect_timeout=5,options='-c default_transaction_read_only=on -c statement_timeout=8000') as c:
    products=c.execute('SELECT loja,url FROM produtos_monitorados WHERE ativo=TRUE ORDER BY id').fetchall()
    offers=c.execute('SELECT loja,produto_id,preco_atual,preco_referencia,atualizada_em FROM ofertas').fetchall()
    history=c.execute('SELECT loja,produto_id,preco,coletado_em FROM historico_precos ORDER BY coletado_em,id').fetchall()
print(json.dumps(dict(products=products,offers=offers,history=history),default=str))
`;

type DatabaseRows = {
  products: Row[];
  offers: Row[];
  history: Row[];
};

export function mapDatabaseProducts(data: DatabaseRows): Product[] {
  return data.products.map((row) => {
    const product = mapProduct(row);
    const offer = data.offers.find(
      (offer) =>
        offer.loja === product.store && offer.produto_id === product.id,
    );

    if (offer) {
      product.price = Number(offer.preco_atual);
      product.reference = Number(offer.preco_referencia);
      product.updated = offer.atualizada_em;
    }

    product.history = data.history
      .filter(
        (observation) =>
          observation.loja === product.store &&
          observation.produto_id === product.id,
      )
      .map((observation) => ({
        price: Number(observation.preco),
        date: observation.coletado_em,
      }));

    return product;
  });
}

export async function readPostgresProducts(): Promise<Product[]> {
  const pythonPath = process.env.SCRAPER_PYTHON || 'python3';
  const runPython = promisify(execFile);
  const { stdout } = await runPython(pythonPath, ['-c', query], {
    timeout: 20_000,
    maxBuffer: 16 * 1024 * 1024,
  });
  return mapDatabaseProducts(JSON.parse(stdout));
}
