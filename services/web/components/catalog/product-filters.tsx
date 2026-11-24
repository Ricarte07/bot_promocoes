import type { Product } from '../../lib/catalog/types';
import {
  ORIGIN_FILTERS, ORIGIN_LABELS, SORT_LABELS, type ProductFilters as ProductFiltersValue, type SortOrder,
} from '../../lib/products/selectors';

export default function ProductFilters({
  products,
  filters,
  order,
  onChange,
  onOrderChange,
  onClear,
}: {
  products: Product[];
  filters: ProductFiltersValue;
  order: SortOrder;
  onChange: (field: keyof ProductFiltersValue, value: string) => void;
  onOrderChange: (value: SortOrder) => void;
  onClear: () => void;
}) {
  const { search, store, minimum, maximum, discount, show } = filters;
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
          placeholder="Busque pelo nome do produto…"
          value={search}
          onChange={(e) => onChange('search', e.target.value)}
        />
      </label>
      <label>
        Mostrar
        <select value={show} onChange={(e) => onChange('show', e.target.value)}>
          <option value="">Todos os produtos</option>
          <option value="promocoes">Só promoções do bot</option>
          {ORIGIN_FILTERS.map((origin) => (
            <option key={origin} value={origin}>Promoções: {ORIGIN_LABELS[origin]}</option>
          ))}
        </select>
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
        Preço mínimo (com cupom)
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
        Preço máximo (com cupom)
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
      <label>
        Ordenar por
        <select value={order} onChange={(e) => onOrderChange(e.target.value as SortOrder)}>
          {(Object.keys(SORT_LABELS) as SortOrder[]).map((key) => (
            <option key={key} value={key}>{SORT_LABELS[key]}</option>
          ))}
        </select>
      </label>
      <button className="clear" type="button" onClick={onClear}>
        Limpar filtros
      </button>
    </form>
  );
}
