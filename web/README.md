# Bufos Promo

Interface Next.js/React do bot. Veja [a configuração compartilhada do Supabase](../docs/supabase.md).

## Executar

Na pasta `web`:

```bash
npm ci
npm run dev
```

Abra http://localhost:3000. Para produção, `npm run build` e `npm start`.

Com `CATALOG_SOURCE=json` (ou sem `DATABASE_URL` e sem seleção explícita), a página lê `../services/scraper/produtos.json` em cada atualização. `PRODUCTS_FILE` permite selecionar outro arquivo (prefira caminho absoluto). Execute os comandos a partir de `web` e mantenha o arquivo disponível no servidor.

A memória do processo Python não é acessível ao Next.js. Por isso o modo JSON mostra links reais, identificação derivada da URL e estados de ausência para preço, imagem e histórico. Nenhum valor é simulado e nenhuma coleta é iniciada pelo painel.

## PostgreSQL / Supabase

O scraper agora grava as tabelas de `sql/schema.sql`; siga `docs/supabase.md` antes de selecionar PostgreSQL. O painel só consulta, sem criar tabelas nem executar coletas. O `.env` da raiz também é carregado, preservando valores já definidos pelo ambiente ou por `web/.env.local`. `CATALOG_SOURCE=postgres` seleciona o banco explicitamente.

O servidor Next.js utiliza um subprocesso Python com a dependência `psycopg`, que precisa estar instalada no ambiente Python. Configure no ambiente do servidor (ou em `web/.env.local`):

```dotenv
DATABASE_URL=postgresql://USUARIO:SENHA_CODIFICADA@HOST:5432/BANCO?sslmode=require
SCRAPER_PYTHON=/caminho/absoluto/para/venv/bin/python
```

`SCRAPER_PYTHON` é opcional, com padrão `python3`. A consulta é somente leitura, com timeout, e credenciais nunca são enviadas ao navegador. Requer hospedagem Node com Python instalado; exportação estática e ambientes Edge não são suportados. O catálogo parte de `ofertas` e usa o identificador persistido pelo coletor, incluindo os produtos descobertos em categorias e outras lojas.

## Comportamento

- Busca, loja, mínimo/máximo e desconto funcionam em conjunto em todas as seções. Limpar restaura a seleção. Produtos com dados ausentes não passam por filtros que exigem esses dados.
- Estatísticas refletem a seleção. Menor preço compara valores nominais de produtos distintos, sem afirmar melhor custo-benefício.
- Desconto compara o preço final (com cupom conhecido) com a maior base entre o primeiro preço coletado e o preço “de” informado pela loja, conforme o domínio; não equivale a um novo evento de promoção.
- Histórico: menor preço de todas as observações disponíveis, gráfico temporal a partir de duas coletas e tabela acessível. Datas em America/Fortaleza.
- Atualização manual consulta novamente a fonte; não executa o scraper. Não há gravações no banco ou no navegador.
- Nome e cupom vêm da oferta persistida, quando coletados. Imagem, estoque e resultado da última tentativa de coleta não estão persistidos. A data mostrada é a da oferta registrada, não uma garantia de preço vigente.
- O catálogo e todo seu histórico são carregados juntos. Para catálogos grandes, uma evolução futura deve incluir paginação e consulta do histórico por produto.

## Verificações

```bash
npm run lint
npx tsc --noEmit
npm run build
```

Verificação manual: combinar filtros, limpar, abrir histórico sem registros, testar arquivo ausente/JSON inválido, navegar por teclado e testar telas de 375px e desktop. Em banco preenchido, conferir menor preço, tabela e gráfico contra `historico_precos`.

Teste da fonte de dados (Node 24): `node --experimental-strip-types --test tests/*.test.mjs`.

Para incluir a leitura de um PostgreSQL real, use TEST_DATABASE_URL e SCRAPER_PYTHON conforme `docs/supabase.md`. O banco descartável de teste não envia notificações.

## Como o código está organizado

- `app/page.tsx` é a entrada do Next.js. Ela espera uma requisição, carrega o catálogo no servidor e mostra uma mensagem enquanto os dados chegam.
- `app/dashboard.tsx` controla a seção selecionada, os filtros e a atualização da tela. A diretiva `use client` permite que esses controles sejam interativos no navegador.
- `components/catalog/` contém as partes visuais: filtros, cartões, estatísticas e histórico. Cada componente recebe os dados de que precisa por propriedades (props).
- `lib/products/` reúne cálculos, filtros e formatação, separados da apresentação.
- `lib/catalog.ts` é o ponto de entrada para carregar os produtos. Os arquivos em `lib/catalog/` isolam a leitura do JSON, a consulta ao PostgreSQL e a conversão para o formato usado na tela. As duas fontes seguem o mesmo contrato de retorno: uma aplicação simples das ideias de Strategy, Adapter e Facade.
- `tests/catalog.test.mjs` verifica a leitura e os estados de erro do catálogo.

Para acompanhar o fluxo, comece em `app/page.tsx`, siga para `lib/catalog.ts` e depois para `app/dashboard.tsx` e seus componentes. As credenciais e o acesso às fontes permanecem no servidor; apenas os dados do catálogo são enviados à interface.

O preço principal é a última observação persistida; a modalidade de pagamento ainda não é gravada como campo próprio. A interface não deve rotular todo preço como Pix. A listagem da Kabum confirma agora cada item na página individual antes de atualizar o banco; uma confirmação malsucedida mantém a última observação, e uma rodada completa faz mais requisições à loja.
