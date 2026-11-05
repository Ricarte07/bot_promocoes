import type { Product } from '../../lib/catalog/types';
import { formatMoney } from '../../lib/products/format';
import { calculateDiscount } from '../../lib/products/selectors';

export default function ProductCard({ product, onShowHistory }: {
  product: Product;
  onShowHistory: (product: Product) => void;
}) {
  const discount = calculateDiscount(product);
  return (
    <tr className="product-row">
      <th scope="row" className="product-name">{product.label}</th>
      <td><span className="store-label">{product.store}</span></td>
      <td className="product-price">
        <strong>{product.price != null ? formatMoney(product.price) : 'Indisponível'}</strong>
        {product.listPrice != null && product.price != null && product.listPrice > product.price &&
          <del>{formatMoney(product.listPrice)}</del>}
      </td>
      <td>{product.coupon ? <span className="coupon-label">{product.coupon}
        {product.couponDiscount != null && product.finalPrice != null &&
          <small>{formatMoney(product.finalPrice)} com cupom</small>}
      </span> : <span className="muted">—</span>}</td>
      <td>{discount != null && discount > 0
        ? <span className="badge">{discount.toFixed(1)}%</span>
        : <span className="muted">—</span>}</td>
      <td><div className="row-actions">
        <button onClick={() => onShowHistory(product)} aria-label={`Ver histórico de ${product.label}`}>Histórico</button>
        <a href={product.url} target="_blank" rel="noopener noreferrer" aria-label={`Ver ${product.label} na loja (nova aba)`}>Ver loja ↗</a>
      </div></td>
    </tr>
  );
}
