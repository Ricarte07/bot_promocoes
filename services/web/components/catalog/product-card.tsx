import type { Product } from '../../lib/catalog/types';
import { formatMoney, formatSeenAgo } from '../../lib/products/format';
import {
  calculateDiscount, hoursSinceSeen, isPromotion, isStale, ORIGIN_LABELS, promotionDiscount,
} from '../../lib/products/selectors';

export default function ProductCard({ product, now, onShowHistory }: {
  product: Product;
  now: number;
  onShowHistory: (product: Product) => void;
}) {
  const discount = calculateDiscount(product);
  const promotion = isPromotion(product, now);
  const botPercent = promotion ? promotionDiscount(product) : null;
  const stale = isStale(product, now);
  const seen = hoursSinceSeen(product, now);
  return (
    <tr className={stale ? 'product-row stale' : 'product-row'} role="row">
      <th scope="row" role="rowheader" className="product-name">{product.label}</th>
      <td role="cell" data-label="Loja">
        <span className="store-label">{product.store}</span>
        {seen !== null && (
          <small className={stale ? 'seen stale-label' : 'seen'}>
            {stale ? 'Desatualizado · ' : 'Visto '}{formatSeenAgo(seen)}
          </small>
        )}
      </td>
      <td role="cell" data-label="Preço atual" className="product-price">
        <strong>{product.price != null ? formatMoney(product.price) : 'Indisponível'}</strong>
        {product.listPrice != null && product.price != null && product.listPrice > product.price &&
          <del>{formatMoney(product.listPrice)}</del>}
      </td>
      <td role="cell" data-label="Cupom">{product.coupon ? <span className="coupon-label">{product.coupon}
        {product.couponDiscount != null && product.finalPrice != null
          ? <small>{formatMoney(product.finalPrice)} com cupom</small>
          : <small>% não informado pela loja</small>}
      </span> : <span className="muted">—</span>}</td>
      <td role="cell" data-label="Desconto">
        {promotion
          ? <span className={product.discountOrigin === 'preco_de_loja' ? 'badge promo-badge unverified' : 'badge promo-badge'}>
              {botPercent != null && <strong>{botPercent.toFixed(1)}%</strong>}
              {product.discountOrigin ? ORIGIN_LABELS[product.discountOrigin] : 'promoção do bot'}
            </span>
          : discount != null && discount > 0
            ? <span className="muted">{discount.toFixed(1)}%</span>
            : <span className="muted">—</span>}
      </td>
      <td role="cell" className="actions-cell"><div className="row-actions">
        <button onClick={() => onShowHistory(product)} aria-label={`Ver histórico de ${product.label}`}>Histórico</button>
        <a href={product.url} target="_blank" rel="noopener noreferrer" aria-label={`Ver ${product.label} na loja (nova aba)`}>Ver loja ↗</a>
      </div></td>
    </tr>
  );
}
