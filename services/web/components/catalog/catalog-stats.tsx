import type { Product } from '../../lib/catalog/types';
import { formatMoney } from '../../lib/products/format';
import { effectivePrice, FRESH_HOURS, isPromotion, isStale, ORIGIN_FILTERS, ORIGIN_LABELS } from '../../lib/products/selectors';

export default function CatalogStats({
  products,
  filtered,
  priced,
  now,
}: {
  products: Product[];
  filtered: Product[];
  priced: Product[];
  now: number;
}) {
  const stale = filtered.filter((p) => isStale(p, now)).length;
  const promotionList = filtered.filter((p) => isPromotion(p, now));
  const promotions = promotionList.length;
  // Quantas promoções há de cada origem: o "de" da loja não conferido pesa diferente.
  const byOrigin = ORIGIN_FILTERS
    .map((origin) => ({ origin, count: promotionList.filter((p) => p.discountOrigin === origin).length }))
    .filter(({ count }) => count > 0);
  return (
    <div className="stats">
      <article>
        <span>Produtos na seleção</span>
        <strong>{filtered.length.toString().padStart(2, '0')}</strong>
        <small>{products.length} no catálogo</small>
      </article>
      <article>
        <span>Vistos nas últimas {FRESH_HOURS} h</span>
        <strong>{(filtered.length - stale).toString().padStart(2, '0')}</strong>
        <small>
          {stale
            ? `${stale} sem atualização há mais de ${FRESH_HOURS} h: o preço pode ter mudado`
            : 'Todos os preços foram conferidos recentemente'}
        </small>
      </article>
      <article>
        <span>Menor preço da seleção</span>
        <strong>{priced.length ? formatMoney(effectivePrice(priced[0])!) : '—'}</strong>
        <small>
          {priced.length
            ? 'Entre produtos diferentes; não indica melhor custo-benefício'
            : 'Aguardando preços acessíveis'}
        </small>
      </article>
      <article>
        <span>Promoções do bot</span>
        <strong>{promotions.toString().padStart(2, '0')}</strong>
        {byOrigin.length > 0 && (
          <ul className="origin-breakdown">
            {byOrigin.map(({ origin, count }) => (
              <li key={origin}><strong>{count}</strong> {ORIGIN_LABELS[origin]}</li>
            ))}
          </ul>
        )}
        <small>
          As mesmas regras do Telegram, vistas nas últimas {FRESH_HOURS} h. Na Kabum o
          desconto é sobre o preço no Pix.
        </small>
      </article>
    </div>
  );
}
