import type { Product } from '../../lib/catalog/types';
import { formatMoney, formatDate } from '../../lib/products/format';
import { calculateDiscount } from '../../lib/products/selectors';

export default function ProductCard({
  product,
  onShowHistory,
}: {
  product: Product;
  onShowHistory: (product: Product) => void;
}) {
  return (
    <article className="product">
      <div className="product-art">
        <span className="store">{product.store}</span>
        <svg
          width="70"
          height="70"
          viewBox="0 0 64 64"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path d="m32 8 22 12v25L32 57 10 45V20L32 8Z M10 20l22 12 22-12M32 32v25M21 14l22 12" />
        </svg>
        <small>Imagem não disponível</small>
      </div>
      <div className="product-body">
        <p className="eyebrow">PRODUTO MONITORADO</p>
        <h2>{product.label}</h2>
        <p className="hint">Identificação extraída da URL</p>
        <div className="price">
          {product.price !== null
            ? formatMoney(product.price)
            : 'Preço indisponível'}
        </div>
        <p className="price-note">
          {product.reference !== null
            ? `Referência: ${formatMoney(product.reference)}`
            : 'Aguardando dados de preço'}{' '}
          {calculateDiscount(product) !== null && (
            <span className="badge">
              {calculateDiscount(product)!.toFixed(1)}% de desconto
            </span>
          )}
        </p>
        <p className="hint">
          {product.updated
            ? `Coleta: ${formatDate(product.updated)}`
            : 'Última coleta não informada'}
        </p>
        <div className="card-actions">
          <a href={product.url} target="_blank" rel="noopener noreferrer">
            Ver na loja ↗<span className="sr-only"> (abre em nova aba)</span>
          </a>
          <button onClick={() => onShowHistory(product)}>Histórico ↗</button>
        </div>
      </div>
    </article>
  );
}
