import type { Product } from '../../lib/catalog/types';
import type { ProductFilters as ProductFiltersValue } from '../../lib/products/selectors';

export default function ProductFilters({
  products,
  filters,
  onChange,
  onClear,
}: {
  products: Product[];
  filters: ProductFiltersValue;
  onChange: (field: keyof ProductFiltersValue, value: string) => void;
  onClear: () => void;
}) {
  const { search, store, minimum, maximum, discount } = filters;
  return (
    <form
      className="filters"
      onSubmit={(e) => e.preventDefault()}
      aria-label="Filtrar produtos"
    >
      <label className="search">
        Buscar produto
        <input
          type="search"
          placeholder="Nome no link do produto…"
          value={search}
          onChange={(e) => onChange('search', e.target.value)}
        />
      </label>
      <label>
        Loja
        <select
          value={store}
          onChange={(e) => onChange('store', e.target.value)}
        >
          <option value="">Todas as lojas</option>
          {[...new Set(products.map((p) => p.store))].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      <label>
        Preço mínimo
        <input
          type="number"
          min="0"
          step="0.01"
          placeholder="R$ 0"
          value={minimum}
          onChange={(e) => onChange('minimum', e.target.value)}
        />
      </label>
      <label>
        Preço máximo
        <input
          type="number"
          min="0"
          step="0.01"
          placeholder="Sem limite"
          value={maximum}
          onChange={(e) => onChange('maximum', e.target.value)}
        />
      </label>
      <label>
        Desconto mínimo
        <select
          value={discount}
          onChange={(e) => onChange('discount', e.target.value)}
        >
          <option value="">Todos</option>
          <option value="5">5%</option>
          <option value="15">15%</option>
          <option value="30">30%</option>
        </select>
      </label>
      <button className="clear" type="button" onClick={onClear}>
        Limpar filtros
      </button>
    </form>
  );
}
