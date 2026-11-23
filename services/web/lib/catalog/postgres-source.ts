import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mapProduct } from './map-product';
import type { Row } from './map-product';
import type { Product } from './types';

// Reutiliza psycopg do scraper, somente para leitura. Não inicia uma coleta.
const query =`
HISTORY='''
SELECT loja,produto_id,preco,coletado_em FROM (
  SELECT loja,produto_id,preco,coletado_em,id,
         lag(preco) OVER w AS anterior,
         lead(id) OVER w AS seguinte
    
  FROM public.historico_precos
  WINDOW w AS (PARTITION BY loja,produto_id ORDER BY coletado_em,id)
) h
WHERE anterior IS DISTINCT FROM preco OR seguinte IS NULL
ORDER BY coletado_em,id
'''


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
    # Só a primeira linha, cada mudança de preço e a mais recente de cada produto.
    # O scraper já grava só mudanças (também de cupom e "de"); a consulta descarta as
    # que não mudam o preço do gráfico.
    history=c.execute(HISTORY).fetchall()
print(json.dumps(dict(offers=offers,history=history),default=str))
`;

type DatabaseRows = {
  offers: Row[];
  history: Row[];
};

export function mapDatabaseProducts(data: DatabaseRows): Product[] {
  // Agrupa o histórico uma vez por produto, em vez de filtrar a lista inteira
  // para cada oferta. A ordem cronológica da consulta é preservada.
  const historyByProduct = new Map<string, Product['history']>();
  for (const observation of data.history) {
    const key = `${observation.loja}:${observation.produto_id}`;
    let points = historyByProduct.get(key);
    if (!points) historyByProduct.set(key, (points = []));
    points.push({ price: Number(observation.preco), date: observation.coletado_em });
  }

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

    product.history = closeAtLastVisit(
      historyByProduct.get(`${product.store}:${product.id}`) ?? [],
      product.price,
      row.atualizada_em,
    );

    return product;
  });
}

// O histórico guarda mudanças, não coletas: a última linha é a última mudança.
// Um ponto em atualizada_em (a última vez que o scraper viu o produto) leva a
// linha do gráfico até hoje com o preço que continua valendo.
export function closeAtLastVisit(
  history: Product['history'],
  price: number | null,
  lastVisit: string | null | undefined,
): Product['history'] {
  const last = history.at(-1);
  if (!last || price == null || !lastVisit) return history;
  const visit = Date.parse(lastVisit);
  if (Number.isNaN(visit) || visit <= Date.parse(last.date)) return history;
  return [...history, { price, date: lastVisit }];
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
