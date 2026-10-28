import type { Product } from '../../lib/catalog/types';
import { formatMoney } from '../../lib/products/format';
import { calculateDiscount } from '../../lib/products/selectors';

export default function CatalogStats({
  products,
  filtered,
  priced,
}: {
  products: Product[];
  filtered: Product[];
  priced: Product[];
}) {
  return (
    <div className="stats">
      <article>
        <span>Produtos na seleção</span>
        <strong>{filtered.length.toString().padStart(2, '0')}</strong>
        <small>{products.length} no catálogo</small>
      </article>
      <article>
        <span>Com preço disponível</span>
        <strong>{priced.length.toString().padStart(2, '0')}</strong>
        <small>Valores registrados pelo coletor</small>
      </article>
      <article>
        <span>Menor preço da seleção</span>
        <strong>{priced.length ? formatMoney(priced[0].price!) : '—'}</strong>
        <small>
          {priced.length
            ? 'Entre produtos diferentes; não indica melhor custo-benefício'
            : 'Aguardando preços acessíveis'}
        </small>
      </article>
      <article>
        <span>Descontos a partir de 15%</span>
        <strong>
          {filtered
            .filter((p) => (calculateDiscount(p) ?? 0) >= 15)
            .length.toString()
            .padStart(2, '0')}
        </strong>
        <small>Em relação ao primeiro preço observado</small>
      </article>
    </div>
  );
}
