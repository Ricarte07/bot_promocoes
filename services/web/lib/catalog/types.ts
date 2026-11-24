// Contratos compartilhados: descrevem os dados, sem acessar banco ou arquivos.
export type Observation = { price: number; date: string };
export type Product = {
  id: string;
  store: string;
  url: string;
  label: string;
  price: number | null;
  reference: number | null;
  listPrice?: number | null;
  // Última vez que o scraper viu o produto (ofertas.atualizada_em).
  updated: string | null;
  history: Observation[];
  coupon?: string | null;
  couponDiscount?: number | null;
  finalPrice?: number | null;
  // O veredito do bot (ofertas.em_promocao): as mesmas regras que decidem o Telegram.
  onSale?: boolean;
};
export type Catalog = {
  products: Product[];
  source: 'json' | 'postgres';
  error: boolean;
  // Quando o servidor leu os dados: base fixa para "visto há X", igual no servidor e no navegador.
  loadedAt: string;
};
