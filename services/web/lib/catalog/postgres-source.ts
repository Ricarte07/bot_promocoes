import { Client, type ClientConfig } from 'pg';
import { mapProduct } from './map-product';
import type { Row } from './map-product';
import type { DiscountOrigin, Product } from './types';

const ORIGINS: DiscountOrigin[] = ['referencia', 'menor_30_dias', 'preco_de_loja'];

// O painel lê o banco direto, com o driver pg (antes chamava o Python do scraper,
// que não existe numa hospedagem como a Vercel). Só leitura: não inicia coleta.
// As datas saem como texto ISO em UTC, iguais no servidor e no navegador.
const ISO = (coluna: string) => `to_char(${coluna} AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')`;

const OFFERS_SQL = `
SELECT loja,produto_id,nome,url,preco_atual,preco_final,preco_de,preco_referencia,
       cupom_codigo,cupom_desconto_percentual,em_promocao,base_desconto,desconto_percentual,
       ${ISO('atualizada_em')} AS atualizada_em
  FROM public.ofertas ORDER BY loja,produto_id`;

// Só a primeira linha, cada mudança de preço e a mais recente de cada produto.
// O scraper já grava só mudanças (também de cupom e "de"); a consulta descarta as
// que não mudam o preço do gráfico.
const HISTORY_SQL = `
SELECT loja,produto_id,preco,${ISO('coletado_em')} AS coletado_em FROM (
  SELECT loja,produto_id,preco,coletado_em,id,
         lag(preco) OVER w AS anterior,
         lead(id) OVER w AS seguinte
  FROM public.historico_precos
  WINDOW w AS (PARTITION BY loja,produto_id ORDER BY coletado_em,id)
) h
WHERE anterior IS DISTINCT FROM preco OR seguinte IS NULL
ORDER BY h.coletado_em,h.id`;

const LOCAL_HOSTS = ['localhost', '127.0.0.1', '::1'];

// Mesmas regras de conexão do scraper (infrastructure/persistencia/postgres.py):
// banco remoto só com SSL, sessão só-leitura, tempo limite e keepalive.
export function connectionConfig(url: string): ClientConfig {
  const parsed = new URL(url);
  const host = parsed.hostname.replace(/^\[|\]$/g, '');
  const remote = host !== '' && !LOCAL_HOSTS.includes(host);
  const sslmode = parsed.searchParams.get('sslmode');
  if (remote && sslmode && !['require', 'verify-ca', 'verify-full'].includes(sslmode)) {
    throw new Error('PostgreSQL remoto exige SSL');
  }
  // Quem decide o SSL é a opção abaixo; se o sslmode ficasse na URL, o pg o usaria por cima dela.
  parsed.searchParams.delete('sslmode');
  return {
    connectionString: parsed.toString(),
    // Como o sslmode=require do libpq: conexão criptografada. O certificado do Supabase
    // é assinado pela autoridade do próprio Supabase, que não está na lista padrão do Node.
    ssl: remote ? { rejectUnauthorized: false } : false,
    connectionTimeoutMillis: 5000,
    statement_timeout: 8000,
    query_timeout: 10000,
    // Uma conexão derrubada em silêncio pelo servidor cai com erro em vez de travar a página.
    keepAlive: true,
    keepAliveInitialDelayMillis: 30000,
    options: '-c default_transaction_read_only=on',
  };
}

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
    // Veredito do bot, gravado pelo scraper: o painel exibe, não recalcula.
    product.onSale = String(row.em_promocao) === 'true';
    product.discountOrigin = ORIGINS.includes(row.base_desconto as DiscountOrigin)
      ? (row.base_desconto as DiscountOrigin) : null;
    product.botDiscount = row.desconto_percentual == null ? null : Number(row.desconto_percentual);

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
  // PANEL_DATABASE_URL: usuário só-leitura próprio do painel (sql/003_painel_somente_leitura.sql).
  const url = process.env.PANEL_DATABASE_URL || process.env.DATABASE_URL;
  if (!url) throw new Error('Defina PANEL_DATABASE_URL ou DATABASE_URL');
  const client = new Client(connectionConfig(url));
  await client.connect();
  try {
    const offers = await client.query<Row>(OFFERS_SQL);
    const history = await client.query<Row>(HISTORY_SQL);
    return mapDatabaseProducts({ offers: offers.rows, history: history.rows });
  } finally {
    await client.end();
  }
}
