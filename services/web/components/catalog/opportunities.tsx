import type { Product } from '../../lib/catalog/types';
import { formatMoney } from '../../lib/products/format';

export default function Opportunities({ priced }: { priced: Product[] }) {
  return (
    <div className="opportunities">
      <section className="panel">
        <p className="eyebrow">NA SUA SELEÇÃO</p>
        <h2>Menores preços disponíveis</h2>
        <p>
          Comparação nominal entre produtos; não é uma recomendação de compra.
        </p>
        {priced.length ? (
          <ol>
            {priced.slice(0, 5).map((p) => (
              <li key={`${p.store}:${p.id}`}>
                <a href={p.url} target="_blank" rel="noopener noreferrer">
                  {p.label} ↗
                </a>
                <strong>{formatMoney(p.price!)}</strong>
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty">Ainda não há preços acessíveis para ordenar.</p>
        )}
      </section>
      <section className="panel seasonal">
        <span className="badge">POSSIBILIDADES, NÃO PREVISÕES</span>
        <h2>
          Contexto ajuda.
          <br />
          Histórico confirma.
        </h2>
        <p>
          Uma promoção anunciada não comprova uma queda de preço. Compare o
          valor com observações anteriores e considere frete e condições de
          pagamento.
        </p>
        <h3>O que observar</h3>
        <p>
          Em períodos frios, vale investigar possíveis ofertas de climatização;
          em trocas de geração, possíveis ofertas de eletrônicos anteriores.
          Essas são hipóteses para pesquisa, não análises dos produtos deste
          catálogo.
        </p>
        <p className="hint">
          Sem dados de sazonalidade, região ou categoria, o painel não atribui
          oportunidades sazonais a produtos específicos.
        </p>
      </section>
    </div>
  );
}
