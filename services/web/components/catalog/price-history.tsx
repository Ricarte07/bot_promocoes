import type { Product } from '../../lib/catalog/types';
import { formatMoney, formatDate } from '../../lib/products/format';
export default function PriceHistory({ product }: { product: Product }) {
  const points = product.history;
  const min = points.length ? Math.min(...points.map((p) => p.price)) : null;
  const max = points.length ? Math.max(...points.map((p) => p.price)) : null;
  const start = points.length ? new Date(points[0].date).getTime() : 0;
  const end = points.length
    ? new Date(points[points.length - 1].date).getTime()
    : 0;
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
            Os preços em memória não são compartilhados com esta interface. O
            modo PostgreSQL existente registra cada coleta e permite consultar a
            evolução aqui.
          </p>
        </div>
      ) : (
        <>
          <p>
            Menor preço registrado{' '}
            <strong className="lowest">{formatMoney(min)}</strong>
          </p>
          {points.length > 1 ? (
            <figure>
              <svg
                viewBox="0 0 640 200"
                role="img"
                aria-label={`Evolução de ${points.length} preços. Mínimo ${formatMoney(min)}. Máximo ${formatMoney(max!)}.`}
              >
                <path d="M20 20V180H620" fill="none" stroke="#ccd5d0" />
                <polyline
                  fill="none"
                  stroke="#187451"
                  strokeWidth="3"
                  points={points
                    .map(
                      (p) =>
                        `${20 + ((new Date(p.date).getTime() - start) / (end - start || 1)) * 600},${170 - ((p.price - min) / (max! - min || 1)) * 140}`,
                    )
                    .join(' ')}
                />
              </svg>
              <figcaption>
                {formatDate(points[0].date)} —{' '}
                {formatDate(points[points.length - 1].date)} · Horário de
                Fortaleza
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
              <caption>Observações registradas (horário de Fortaleza)</caption>
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
