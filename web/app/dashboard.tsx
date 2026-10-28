'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Brand from './brand';
import ThemeToggle from './theme-toggle';
import type { Catalog, Product } from '../lib/catalog/types';
import ProductCard from '../components/catalog/product-card';
import PriceHistory from '../components/catalog/price-history';
import CatalogStats from '../components/catalog/catalog-stats';
import ProductFilters from '../components/catalog/product-filters';
import Opportunities from '../components/catalog/opportunities';
import {
  EMPTY_FILTERS,
  filterProducts,
  hasInvalidPriceRange,
  sortByLowestPrice,
  type ProductFilters as Filters,
} from '../lib/products/selectors';
export default function Dashboard({ catalog }: { catalog: Catalog }) {
  const [section, setSection] = useState('Produtos');
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selected, setSelected] = useState('');
  const [pending, startTransition] = useTransition();
  const router = useRouter();
  function clearFilters() {
    setFilters(EMPTY_FILTERS);
  }
  function changeFilter(field: keyof Filters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }));
  }
  function showHistory(product: Product) {
    setSelected(`${product.store}:${product.id}`);
    setSection('Histórico');
  }

  const products = catalog.products;
  const invalidRange = hasInvalidPriceRange(filters);
  const filtered = filterProducts(products, filters);
  const priced = sortByLowestPrice(filtered);
  const chosen =
    filtered.find((p) => `${p.store}:${p.id}` === selected) ?? filtered[0];
  const refresh = () => startTransition(() => router.refresh());
  return (
    <>
      <a href="#content" className="skip">
        Pular para o conteúdo
      </a>
      <header>
        <div className="header-inner">
          <Link href="/" className="brand" aria-label="Bufos Promo início">
            <Brand tagline />
          </Link>
          <div className="header-actions">
            <ThemeToggle />
            <span className="source">
              <i />
              {catalog.source === 'json' ? 'Catálogo local' : 'PostgreSQL'}
            </span>
          </div>
        </div>
      </header>
      <main id="content">
        <div className="intro">
          <div>
            <p className="eyebrow">SEU RADAR DE ECONOMIA</p>
            <h1>
              De olho no preço certo<span>.</span>
            </h1>
          </div>
          <button className="refresh" onClick={refresh} disabled={pending}>
            {pending ? 'Atualizando…' : '↻ Atualizar dados'}
          </button>
        </div>
        <CatalogStats products={products} filtered={filtered} priced={priced} />
        <nav className="tabs" aria-label="Seções do painel">
          {['Produtos', 'Histórico', 'Oportunidades'].map((s) => (
            <button
              key={s}
              aria-current={section === s ? 'page' : undefined}
              onClick={() => setSection(s)}
            >
              {s}
              {s === 'Produtos' && <span>{products.length}</span>}
            </button>
          ))}
        </nav>
        {catalog.error ? (
          <section className="empty error" role="alert">
            <h2>Não foi possível carregar os produtos</h2>
            <p>
              {catalog.source === 'postgres'
                ? 'Verifique a conexão, as tabelas existentes e o Python com psycopg no servidor.'
                : 'Verifique se o arquivo de produtos existe e contém uma lista válida de lojas e URLs.'}
            </p>
            <button onClick={refresh} disabled={pending}>
              Tentar novamente
            </button>
          </section>
        ) : (
          <>
            <aside className="notice">
              <strong>
                {catalog.source === 'json'
                  ? 'Links disponíveis. Preços ainda não compartilhados.'
                  : 'Preços da última coleta registrada.'}
              </strong>
              <span>
                {catalog.source === 'json'
                  ? 'O catálogo usa as URLs reais do scraper. Preços e histórico em memória não estão acessíveis nesta página.'
                  : 'Atualizar a página consulta os registros; não inicia uma coleta. Confirme o valor final na loja.'}
              </span>
            </aside>
            <ProductFilters
              products={products}
              filters={filters}
              onChange={changeFilter}
              onClear={clearFilters}
            />
            {invalidRange && (
              <p role="alert" className="error">
                O preço mínimo deve ser menor ou igual ao máximo.
              </p>
            )}
            <p className="result-count" role="status">
              {filtered.length} produtos encontrados
              {(filters.minimum || filters.maximum || filters.discount) &&
                ' · Produtos sem o dado filtrado ficam fora da seleção.'}
            </p>
            {section === 'Produtos' &&
              (filtered.length ? (
                <div className="product-grid">
                  {filtered.map((p) => (
                    <ProductCard
                      key={`${p.store}:${p.id}`}
                      product={p}
                      onShowHistory={showHistory}
                    />
                  ))}
                </div>
              ) : (
                <div className="empty">
                  <h2>
                    {products.length
                      ? 'Nenhum produto corresponde aos filtros'
                      : 'Nenhum produto cadastrado'}
                  </h2>
                  <p>
                    {products.length
                      ? 'Experimente ampliar a faixa de preços ou limpar a seleção.'
                      : 'Os produtos aparecerão quando cadastrados na fonte utilizada pelo scraper.'}
                  </p>
                  {products.length > 0 && (
                    <button onClick={clearFilters}>Limpar filtros</button>
                  )}
                </div>
              ))}
            {section === 'Histórico' && (
              <>
                {chosen ? (
                  <>
                    <label className="history-selector">
                      Selecionar produto
                      <select
                        value={`${chosen.store}:${chosen.id}`}
                        onChange={(e) => setSelected(e.target.value)}
                      >
                        {filtered.map((p) => (
                          <option
                            key={`${p.store}:${p.id}`}
                            value={`${p.store}:${p.id}`}
                          >
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <PriceHistory product={chosen} />
                  </>
                ) : (
                  <div className="empty">
                    <h2>Nenhum produto na seleção</h2>
                    <p>
                      Limpe os filtros para consultar os produtos disponíveis.
                    </p>
                    <button onClick={clearFilters}>Limpar filtros</button>
                  </div>
                )}
              </>
            )}
            {section === 'Oportunidades' && <Opportunities priced={priced} />}
          </>
        )}
        <footer>
          <span className="brand">
            <Brand />
          </span>
          <p>Dados disponíveis, decisões mais conscientes.</p>
          <span>Valores sujeitos a alteração na loja.</span>
        </footer>
      </main>
    </>
  );
}
