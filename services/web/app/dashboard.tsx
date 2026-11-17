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
  const chosenIndex = chosen ? filtered.indexOf(chosen) : -1;
  function navigateHistory(direction: number) {
    const product = filtered[chosenIndex + direction];
    if (product) setSelected(`${product.store}:${product.id}`);
  }
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
        <nav className="section-nav" aria-label="Seções do painel">
          {['Produtos', 'Histórico'].map((s) => (
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
          <div className="header-actions">
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main id="content">
        <div className="intro">
          <div>
            <p className="eyebrow">MONITORAMENTO DE PREÇOS</p>
            <h1>
              Acompanhe cada preço<span>.</span>
            </h1>
          </div>
          <button className="refresh" onClick={refresh} disabled={pending}>
            {pending ? 'Atualizando…' : '↻ Atualizar dados'}
          </button>
        </div>
        <CatalogStats products={products} filtered={filtered} priced={priced} />
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
                <div className="product-table-wrap" tabIndex={0} role="region" aria-label="Lista de produtos">
                  <table className="product-table">
                    <caption className="sr-only">Produtos monitorados e seus últimos preços registrados</caption>
                    <thead><tr><th scope="col">Produto</th><th scope="col">Loja</th><th scope="col">Preço atual</th><th scope="col">Cupom</th><th scope="col">Desconto</th><th scope="col">Ações</th></tr></thead>
                    <tbody>
                  {filtered.map((p) => (
                    <ProductCard
                      key={`${p.store}:${p.id}`}
                      product={p}
                      onShowHistory={showHistory}
                    />
                  ))}
                    </tbody>
                  </table>
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
                    <div className="history-navigation">
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
                              {p.label} · {p.store}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="history-navigation-actions" role="group" aria-label="Trocar produto do histórico">
                        <button
                          onClick={() => navigateHistory(-1)}
                          disabled={chosenIndex <= 0}
                        >
                          ← Anterior
                        </button>
                        <span role="status">{chosenIndex + 1} de {filtered.length}</span>
                        <button
                          onClick={() => navigateHistory(1)}
                          disabled={chosenIndex >= filtered.length - 1}
                        >
                          Próximo →
                        </button>
                      </div>
                      <p className="history-navigation-hint">Use a busca acima para encontrar um produto pelo nome.</p>
                    </div>
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
