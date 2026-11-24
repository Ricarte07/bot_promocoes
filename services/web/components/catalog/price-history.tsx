import type { Product } from '../../lib/catalog/types';
import { formatMoney, formatDate, formatShortDate } from '../../lib/products/format';
import { CHART, lowestLineY, stepPath } from '../../lib/products/chart';
export default function PriceHistory({ product }: { product: Product }) {
  const points = product.history;
  const min = points.length ? Math.min(...points.map((p) => p.price)) : null;
  const max = points.length ? Math.max(...points.map((p) => p.price)) : null;
  return (
    <section className="history">
      <div className="section-heading">
        <div>
          <p className="eyebrow">HISTÓRICO DE PREÇOS</p>
          <h2>{product.label}</h2>
        </div>
        <span className="badge">{points.length} registros</span>
      </div>
      {min === null ? (
        <div className="empty">
          <span aria-hidden="true">⌁</span>
          <h3>Ainda não há histórico disponível</h3>
          <p>
            O histórico aparece quando o scraper grava no PostgreSQL. Ele guarda a
            primeira coleta e cada mudança de preço, cupom ou preço &ldquo;de&rdquo;.
          </p>
        </div>
      ) : (
        <>
          <p>
            Menor preço registrado{' '}
            <strong className="lowest">{formatMoney(min)}</strong>
          </p>
          {points.length > 1 ? (
            <figure className="chart">
              <div className="chart-plot">
                {/* Preço que nunca mudou: um rótulo só, no meio, na altura da linha. */}
                <div className={max === min ? 'chart-y flat' : 'chart-y'} aria-hidden="true">
                  {max !== min && <span>{formatMoney(max!)}</span>}
                  <span>{formatMoney(min)}</span>
                </div>
                <svg
                  viewBox={`0 0 ${CHART.width} ${CHART.height}`}
                  preserveAspectRatio="none"
                  role="img"
                  aria-label={`Preço em degraus de ${formatShortDate(points[0].date)} a ${formatShortDate(points[points.length - 1].date)}. Mínimo ${formatMoney(min)}, máximo ${formatMoney(max!)}.`}
                >
                  <line className="chart-axis" x1="0" y1={CHART.height} x2={CHART.width} y2={CHART.height} vectorEffect="non-scaling-stroke" />
                  <line className="chart-lowest" x1="0" y1={lowestLineY(points)} x2={CHART.width} y2={lowestLineY(points)} vectorEffect="non-scaling-stroke" />
                  <path className="chart-line" d={stepPath(points)} vectorEffect="non-scaling-stroke" />
                </svg>
                <span aria-hidden="true" />
                <div className="chart-x" aria-hidden="true">
                  <span>{formatShortDate(points[0].date)}</span>
                  <span>{formatShortDate(points[points.length - 1].date)}</span>
                </div>
              </div>
              <figcaption>
                <span className="chart-key" aria-hidden="true" /> Menor preço registrado ·{' '}
                {formatDate(points[0].date)} — {formatDate(points[points.length - 1].date)} ·
                horário de Brasília
              </figcaption>
            </figure>
          ) : (
            <p>
              Uma coleta registrada. O gráfico aparece a partir de duas
              observações.
            </p>
          )}
          <div className="table-wrap">
            <table>
              <caption>Primeira coleta, mudanças de preço e coleta mais recente (horário de Brasília)</caption>
              <thead>
                <tr>
                  <th>Data da coleta</th>
                  <th>Preço</th>
                </tr>
              </thead>
              <tbody>
                {points.map((p, i) => (
                  <tr key={i}>
                    <td>{formatDate(p.date)}</td>
                    <td>
                      {formatMoney(p.price)}{' '}
                      {p.price === min && (
                        <span className="badge">Menor preço</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
