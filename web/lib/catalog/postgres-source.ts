import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mapProduct } from './map-product';
import type { Row } from './map-product';
import type { Product } from './types';

// Reutiliza psycopg do scraper, somente para leitura. Não inicia uma coleta.
const query = `
import os,json,psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict
params=conninfo_to_dict(os.environ['DATABASE_URL'])
host=params.get('host','')
if host and not host.startswith('/') and host not in ('localhost','127.0.0.1','::1'):
    if params.get('sslmode','require') not in ('require','verify-ca','verify-full'):
        raise ValueError('PostgreSQL remoto exige SSL')
    params.setdefault('sslmode','require')
with psycopg.connect(**params,row_factory=dict_row,connect_timeout=5,prepare_threshold=None,options='-c default_transaction_read_only=on -c statement_timeout=8000') as c:
    offers=c.execute('SELECT loja,produto_id,nome,url,preco_atual,preco_final,preco_de,preco_referencia,cupom_codigo,cupom_desconto_percentual,atualizada_em FROM public.ofertas ORDER BY loja,produto_id').fetchall()
    history=c.execute('SELECT loja,produto_id,preco,coletado_em FROM public.historico_precos ORDER BY coletado_em,id').fetchall()
print(json.dumps(dict(offers=offers,history=history),default=str))
`;

type DatabaseRows = {
  offers: Row[];
  history: Row[];
};

export function mapDatabaseProducts(data: DatabaseRows): Product[] {
  return data.offers.map((row) => {
    const product = mapProduct(row);
    product.id = row.produto_id;
    product.label = row.nome || product.label;
    product.price = Number(row.preco_atual);
    product.reference = Number(row.preco_referencia);
    product.listPrice = row.preco_de == null ? null : Number(row.preco_de);
    product.updated = row.atualizada_em;
    product.coupon = row.cupom_codigo || null;
    product.couponDiscount = row.cupom_desconto_percentual == null ? null : Number(row.cupom_desconto_percentual);
    product.finalPrice = Number(row.preco_final);

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
