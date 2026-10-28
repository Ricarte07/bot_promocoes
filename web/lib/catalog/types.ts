// Contratos compartilhados: descrevem os dados, sem acessar banco ou arquivos.
export type Observation = { price: number; date: string };
export type Product = {
  id: string;
  store: string;
  url: string;
  label: string;
  price: number | null;
  reference: number | null;
  updated: string | null;
  history: Observation[];
};
export type Catalog = {
  products: Product[];
  source: 'json' | 'postgres';
  error: boolean;
};
