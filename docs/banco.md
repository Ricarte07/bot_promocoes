# Banco de dados

O bot guarda no PostgreSQL os produtos encontrados (inclusive os de categorias),
nome, link, preços, cupons e uma observação por coleta. O banco é também a
**memória do bot**: o primeiro preço visto de cada produto (base do desconto) e se
a promoção já foi anunciada. Sem essa memória, cada reinício reanuncia tudo.

O código usa SQL puro (`psycopg`), sem SDK do Supabase: qualquer PostgreSQL serve,
e quem escolhe é a `DATABASE_URL` do `.env`.

## Quem usa qual banco

| Banco | Onde | Para quê | Eventos |
| --- | --- | --- | --- |
| **Oficial** | Postgres no Docker, no notebook da empresa | O bot "de verdade", ligado ao Telegram | `redis` |
| **Testes compartilhados** | Supabase | Experimentos com dados reais entre a equipe | sempre `console` |
| **Testes automáticos** | Banco descartável (`TEST_DATABASE_URL`) | `pytest` e testes da web; o CI usa um container próprio | — |

**Regra:** só o banco oficial roda com `--eventos redis` (que leva ao Telegram).
Cada banco tem a própria memória; dois bancos ligados ao Telegram mandariam a mesma
promoção duas vezes.

## Configuração inicial

Na raiz do projeto:

```bash
cp .env.example .env
python -m venv services/scraper/.venv
```

Instale as dependências do scraper (Linux/macOS e Windows/Git Bash, respectivamente):

```bash
services/scraper/.venv/bin/pip install -r services/scraper/requirements.txt
services/scraper/.venv/Scripts/pip install -r services/scraper/requirements.txt
```

Se o `.env` já existe, edite-o preservando os valores atuais; não execute `cp` por
cima. O arquivo é ignorado pelo Git. Nunca use o prefixo `NEXT_PUBLIC_` para
credenciais. Todas as variáveis estão explicadas no [`.env.example`](../.env.example).

## Banco oficial (Docker)

1. No `.env`, defina `POSTGRES_PASSWORD` e use a mesma senha na `DATABASE_URL`
   (`postgresql://promo:SENHA@127.0.0.1:5432/promo`).
2. Suba o banco (e o Redis, se for usar o Telegram):

   ```bash
   docker compose up -d postgres redis
   ```

   Na **primeira** subida, com o volume vazio, o container aplica `sql/schema.sql`
   sozinho. Nas seguintes, os dados continuam no volume `postgres-dados`.
3. Confira a conexão e as tabelas (só leitura, não envia nada), em `services/scraper`:

   ```bash
   python -m interfaces.banco
   ```

A porta fica presa em `127.0.0.1`: o banco não aparece na rede da empresa.

Use `127.0.0.1`, e não `localhost`, nas URLs do banco e do Redis. No Windows,
`localhost` tenta primeiro o endereço IPv6 `::1`, onde o Docker não escuta; a
tentativa não é recusada, fica esperando, e cada conexão atrasa de 5 a 10 segundos
(ou trava, quando não há timeout).

**Recriar do zero** (apaga todos os dados e o histórico do banco oficial):

```bash
docker compose down -v
docker compose up -d postgres
```

Mudanças futuras no `sql/schema.sql` **não** são reaplicadas num volume que já
existe: precisam de uma migração (um `ALTER TABLE` rodado à parte) ou da recriação acima.

## Supabase (testes compartilhados)

1. No painel do Supabase, confira o nome e o identificador do projeto correto.
2. Em **Connect**, copie a conexão **Session pooler**, porta 5432. É a opção
   indicada para processos persistentes em redes IPv4. Use exatamente o endereço
   mostrado no painel. A conexão direta serve se a máquina tiver IPv6.
3. Troque a `DATABASE_URL` do `.env` pela do Supabase (há um exemplo comentado no
   `.env.example`), com a senha de **banco** e `?sslmode=require`. Codifique
   caracteres especiais da senha com percent-encoding. `require` criptografa; para
   validar também o certificado, use `sslmode=verify-full&sslrootcert=/caminho/certificado.crt`.
4. Com Transaction pooler (6543), os prepared statements automáticos já estão
   desabilitados nos clientes Python; a transação é por produto.
5. Rode sempre com `--eventos console`.

O plano gratuito pausa o projeto após 7 dias sem atividade e tem limite de espaço:
confira o uso em **Usage** no painel.

### Criar as tabelas no Supabase sem sobrescrever nada

No SQL Editor **do projeto conferido**, execute primeiro:

```sql
select current_database(), current_user;
select table_schema, table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('ofertas','referencias_precos','historico_precos','produtos_monitorados','eventos_pendentes');
```

Se nenhuma das cinco tabelas aparecer, execute o conteúdo de `sql/schema.sql` no
mesmo editor. Se alguma já existir, **não apague nada**: compare as colunas com o
script e prepare uma migração específica. O script roda numa única transação e
falha em vez de ignorar tabelas incompatíveis.

As quatro tabelas têm RLS habilitado, sem políticas públicas, e os privilégios de
PUBLIC, anon, authenticated e service_role são revogados. O backend usa a conexão
privada do proprietário, que trabalha com as tabelas apesar do RLS. Não há endpoint
público da Data API; a web lê no servidor e entrega só os dados do catálogo. Para
adotar um papel dedicado depois, conceda só os acessos necessários e crie políticas
para ele; não libere acesso público para corrigir uma falha.

Documentação: [conexões](https://supabase.com/docs/guides/database/connecting-to-postgres),
[RLS](https://supabase.com/docs/guides/database/postgres/row-level-security),
[pausa por inatividade](https://supabase.com/docs/guides/platform/free-project-pausing).

## Variáveis

| Variável | Uso |
| --- | --- |
| `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD` | Usados pelo `docker compose` para criar o banco oficial. |
| `DATABASE_URL` | Conexão privada do PostgreSQL, compartilhada por scraper e web. |
| `PERSISTENCIA` | `postgres` (padrão) guarda estado e histórico; `memoria` é explicitamente temporário. |
| `FONTE_PRODUTOS` | `json` (padrão) lê `produtos.json`; `postgres` lê endereços ativos de `produtos_monitorados`. |
| `EVENTOS_TRANSPORTE` | `console` (padrão seguro), `redis` ou `postgres`. Independente da fonte e da persistência. |
| `REDIS_URL` | Obrigatória com transporte Redis; também usada pelo notifier. |
| `PANEL_DATABASE_URL` | Opcional, recomendada: conexão só-leitura da web (veja "Usuário só-leitura do painel"). Sem ela, a web usa a `DATABASE_URL`. |
| `CATALOG_SOURCE` | `postgres` ou `json`. Sem valor, a web escolhe PostgreSQL se houver `DATABASE_URL`. |
| `SCRAPER_PYTHON` | Só os testes da web: o Python do scraper, usado para gravar dados de teste. O painel em si lê o banco pelo driver `pg`. |
| `PRODUCTS_FILE` | Caminho opcional do JSON da web. O scraper usa `--produtos`. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Só o notifier; desnecessários para testar armazenamento. |
| `TEST_DATABASE_URL` | Só testes: banco separado com nome terminado em `_test` e usuário com CREATEDB. |

Scraper, notifier e web carregam o `.env` da raiz; variáveis já definidas no
ambiente (ou em `services/web/.env.local`, para a web) têm prioridade. Execute a web
dentro de `services/web/` e o notifier dentro de `services/notifier/`. Reinicie os
serviços após mudar a configuração.

## Usuário só-leitura do painel

A web só lê `ofertas` e `historico_precos`. Por padrão ela usa a `DATABASE_URL`
do scraper, que pode escrever, e se protege só com uma opção de sessão. Para que
o próprio banco recuse qualquer escrita vinda do painel:

1. Rode `sql/003_painel_somente_leitura.sql` uma vez (no SQL Editor do Supabase),
   trocando `TROQUE_ESTA_SENHA` por uma senha forte, só com letras e números.
2. No `.env` da raiz, acrescente `PANEL_DATABASE_URL`, igual à `DATABASE_URL` mas
   com o usuário e a senha novos. No Supabase, pelo Session pooler, o usuário é
   `painel_leitura.<id do projeto>` (o mesmo sufixo que aparece em `postgres.<id>`).
3. Reinicie a web.

O usuário só tem `SELECT` nessas duas tabelas e não enxerga as demais. Mesmo
desligando o modo só-leitura da sessão, `INSERT`, `UPDATE` e `DELETE` são
recusados por falta de permissão.

## Executar sem enviar notificações

Dentro de `services/scraper`, com o `.venv` ativo (`source .venv/bin/activate`, ou
`source .venv/Scripts/activate` no Git Bash):

```bash
# Só consulta tabelas e mostra contagens. Valida a conexão configurada.
python -m interfaces.banco
# Coleta real e grava no banco; promoções aparecem só no terminal.
python -m interfaces.agendador --persistencia postgres --eventos console --uma-vez
```

Não inicie o notifier para esse teste. O console mantém o estado da promoção: uma
promoção exibida nele não será reenviada só por mudar depois para Redis.

Os endereços e categorias podem continuar em `produtos.json`. Para usar o cadastro
no banco:

```bash
python -m interfaces.banco --importar-json
python -m interfaces.agendador --fonte-produtos postgres --eventos console --uma-vez
```

A importação atualiza tipo/páginas dos endereços já cadastrados, preserva `ativo` e
não apaga os ausentes do JSON. Para acrescentar uma categoria pelo SQL:

```sql
insert into public.produtos_monitorados (loja,url,tipo,paginas)
values ('kabum','https://www.kabum.com.br/hardware','listagem',2)
on conflict (loja,url) do nothing;
```

Cada produto encontrado numa categoria vira uma linha de `ofertas` e novas linhas de
histórico. Produtos coletados continuam no catálogo mesmo se a categoria for
desativada; a data informa quando foram vistos pela última vez.

O histórico guarda **mudanças, não coletas**: uma linha nova só quando preço, "de",
preço final ou cupom mudam. A última vez que o produto foi visto fica em
`ofertas.atualizada_em`, e o gráfico do painel vai até ela. Assim o volume cresce com
as mudanças de preço, não com o número de rodadas. Para compactar um histórico gravado
antes disso, rode `sql/002_historico_so_mudancas.sql` uma vez, com o scraper parado
(opcional: apaga só as linhas repetidas).

Quando a loja confirma que o produto está sem estoque, a linha de `ofertas` é removida;
o histórico fica, e o preço de referência continua guardado em `referencias_precos`,
para que o produto, ao voltar, seja comparado com o mesmo preço. Em bancos criados antes
dessa tabela, aplique `sql/001_ofertas_ativas.sql` uma vez, com o scraper parado.

Modo local sem banco nem Redis (a memória se perde ao encerrar):

```bash
# services/scraper
python -m interfaces.agendador --persistencia memoria --fonte-produtos json --eventos console --uma-vez
# services/web (outro terminal)
CATALOG_SOURCE=json npm run dev
```

Falha no PostgreSQL encerra a coleta com erro, sem trocar para memória em silêncio.
A web mostra erro de leitura, sem trocar a fonte nem exibir credenciais.

## Escolher a entrega dos eventos

```bash
# services/scraper
python -m interfaces.agendador --eventos console --uma-vez
python -m interfaces.agendador --eventos redis --uma-vez
python -m interfaces.agendador --eventos postgres --persistencia postgres --uma-vez
```

Redis é a única fila que o notifier consome: suba-o com `docker compose up -d redis`
e rode o notifier conforme o README dele. `console` não envia nada; `postgres` só
grava avisos em `eventos_pendentes` (enfileirado, não enviado) e exige persistência
PostgreSQL, na mesma transação da oferta.

A referência inicial, o preço final anterior e `em_promocao` são recuperados antes
de cada coleta; carregar o banco não gera evento. O bloqueio por produto também
protege a primeira inserção contra coletores concorrentes. O histórico registra
cada observação, mesmo quando o preço não muda.

## Testes com PostgreSQL

Na pasta `services/scraper`, `pytest -q` roda tudo; sem `TEST_DATABASE_URL`, os seis
testes de integração com PostgreSQL ficam pulados. Para rodá-los no Postgres do
Docker, crie uma vez o banco base de testes:

```bash
docker exec promo-postgres createdb -U promo bot_promocoes_test
export TEST_DATABASE_URL='postgresql://promo:SENHA@127.0.0.1:5432/bot_promocoes_test?sslmode=disable'
pytest -q
```

Cada teste cria um banco de nome aleatório, aplica o SQL e remove **só esse banco**
no final; nenhuma tabela do banco oficial é tocada. O usuário precisa de CREATEDB e,
para o teste de permissões, CREATEROLE (o usuário do container tem os dois). Nunca
aponte `TEST_DATABASE_URL` para o banco oficial nem para o Supabase.

Na pasta `services/web`, com o mesmo `TEST_DATABASE_URL`:

```bash
export SCRAPER_PYTHON='../scraper/.venv/bin/python'   # Git Bash: ../scraper/.venv/Scripts/python.exe
node --experimental-strip-types --test tests/*.test.mjs
```

O teste da web grava um produto pelo caso de uso Python num banco descartável e
confere a leitura pelo painel. O CI (`.github/workflows/ci.yml`) roda tudo isso
num Postgres próprio a cada PR.

## O que falta para substituir o Redis

Falta um adaptador no notifier que leia `eventos_pendentes` e reutilize o JSON de
`payload` (contrato de `docs/evento-promocao.md`). Plano, **não implementado**:

1. Numa transação curta, selecionar avisos não enviados, disponíveis e sem reserva
   válida com `FOR UPDATE SKIP LOCKED`; atualizar `reservado_ate`, `reserva_token`
   único e incrementar `tentativas`. Commit antes da chamada ao Telegram.
2. Enviar fora da transação, com reserva de validade limitada, para dois processos
   não pegarem o mesmo aviso.
3. Após sucesso, atualizar `enviado_em` só se o token da reserva ainda for seu. Após
   falha, registrar erro sanitizado e definir `disponivel_em` com espera crescente;
   liberar a reserva. Limitar tentativas.
4. Recuperar reservas expiradas após quedas e testar concorrência, falha de rede,
   timeouts e reinício antes de desligar o Redis.

A gravação de oferta + histórico + aviso só é atômica no transporte PostgreSQL.
Redis e console não participam da transação: pode haver publicação seguida de falha
no commit. Mesmo com a fila no banco, uma queda depois de o Telegram aceitar e antes
da confirmação pode gerar reenvio. **Não há garantia de entrega sem duplicações.**
