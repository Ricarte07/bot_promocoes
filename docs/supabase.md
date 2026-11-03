# PostgreSQL no Supabase

A coleta continua usando as mesmas lojas, regras de desconto e contrato de eventos.
O banco passa a guardar os produtos encontrados (inclusive os de categorias), nome,
link, preços, cupons realmente encontrados e uma observação por coleta. Não há
imagens, estoque ou condições de cupom inventadas.

## Configuração inicial

Na pasta oficial do projeto:

```bash
cp .env.example .env
python3 -m venv services/scraper/.venv
services/scraper/.venv/bin/pip install -r services/scraper/requirements.txt
```

Se `.env` já existe, edite-o preservando os valores atuais; não execute `cp` por cima.
O arquivo é ignorado pelo Git. Nunca use o prefixo `NEXT_PUBLIC_` para credenciais.

1. No painel Supabase, confira o nome e o identificador do projeto correto.
2. Em **Connect**, copie a conexão **Session pooler**, porta 5432. É a opção
   indicada aqui para processos persistentes em redes IPv4. Não invente o host:
   use exatamente o endereço mostrado no painel. A conexão direta é adequada
   se o servidor tiver IPv6 (ou o projeto tiver o recurso IPv4).
3. Preencha `DATABASE_URL` no `.env` da raiz, com a senha de **banco** e
   `?sslmode=require`. Codifique caracteres especiais da senha com percent-encoding.
   `require` criptografa; para validar também o certificado/hostname, use
   `sslmode=verify-full&sslrootcert=/caminho/certificado.crt`, com o certificado
   obtido no painel. `sslmode=disable` fica reservado ao PostgreSQL local de testes.
4. Se usar Transaction pooler (6543) em outro ambiente, prepared statements
   automáticos já estão desabilitados nos dois clientes Python. A transação é por
   produto e não depende de estado de sessão. Session pooler é o caminho padrão
   documentado para este projeto.

Documentação consultada: [conexões](https://supabase.com/docs/guides/database/connecting-to-postgres),
[RLS](https://supabase.com/docs/guides/database/postgres/row-level-security),
[changelog](https://supabase.com/changelog),
[permissões da Data API](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically).
A integração usa SQL direto; não requer chave anon, service_role ou SDK Supabase.

## Criar as tabelas sem sobrescrever um esquema existente

No SQL Editor **do projeto conferido**, execute primeiro:

```sql
select current_database(), current_user;
select table_schema, table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('ofertas','historico_precos','produtos_monitorados','eventos_pendentes');
```

Se não aparecer nenhuma dessas quatro tabelas, execute o conteúdo de
`sql/schema.sql` no mesmo editor. Se alguma já existir, **não apague nada**:
compare suas colunas/restrições com o script antes de preparar uma migração
específica. O script falha em vez de ignorar tabelas incompatíveis e roda numa
única transação. Não é executado automaticamente na partida.

As quatro tabelas têm RLS habilitado, sem políticas públicas. Os privilégios de
PUBLIC, anon, authenticated e service_role nessas tabelas e sequências são
revogados. O backend usa a conexão privada do proprietário (`postgres` no
Supabase), que consegue trabalhar com as tabelas apesar do RLS. Não há endpoint
público da Data API. A interface web lê no servidor e entrega só dados do catálogo.
Para adotar um papel dedicado depois, conceda apenas os acessos necessários e
crie políticas para esse papel; não libere acesso público para corrigir uma falha.

## Variáveis

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` | Conexão privada do PostgreSQL, compartilhada por scraper e servidor web. |
| `PERSISTENCIA` | `postgres` (padrão) guarda estado e histórico; `memoria` é explicitamente temporário. |
| `FONTE_PRODUTOS` | `json` (padrão) lê `produtos.json`; `postgres` lê endereços ativos de `produtos_monitorados`. |
| `EVENTOS_TRANSPORTE` | `console` (padrão seguro), `redis` ou `postgres`. Independente da fonte e da persistência. |
| `REDIS_URL` | Obrigatória com transporte Redis; também utilizada pelo Go. |
| `CATALOG_SOURCE` | `postgres` ou `json`. Sem valor, a web escolhe PostgreSQL se houver DATABASE_URL. |
| `SCRAPER_PYTHON` | Interpretador usado pela web; precisa ter psycopg instalado. Padrão `python3`. |
| `PRODUCTS_FILE` | Caminho opcional do JSON da web. O scraper usa `--produtos`. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Apenas notifier Go; desnecessários para testar armazenamento. |
| `TEST_DATABASE_URL` | Somente testes: banco local separado com nome terminado em `_test` e usuário com CREATEDB. |

Scraper e Go já carregam o `.env` da raiz. A web agora também carrega esse arquivo;
variáveis já definidas no ambiente ou por `web/.env.local` têm prioridade. Execute a
web dentro de `web/` e o Go dentro de `services/notifier/`. Reinicie os serviços
após mudar a configuração. Para a web, ajuste SCRAPER_PYTHON para o caminho do
ambiente virtual (o exemplo relativo funciona quando iniciada em `web/`).

## Executar sem enviar notificações

Dentro de `services/scraper`, com `.venv` ativo:

```bash
source .venv/bin/activate
# Só consulta tabelas e mostra contagens. Valida a conexão realmente configurada.
python -m interfaces.banco
# Coleta real e grava no banco; promoções aparecem só no terminal.
python -m interfaces.agendador --persistencia postgres --eventos console --uma-vez
```

Não inicie o notifier para esse teste. Esses comandos não enviam Telegram/WhatsApp.
O console mantém o estado da promoção: uma promoção exibida nele não será reenviada
só por mudar depois para Redis. Para repetir um experimento, use o banco de testes,
não apague a referência do banco real.

Os endereços e categorias podem continuar em `produtos.json`, sem importar nada.
Para optar pelo cadastro no banco:

```bash
python -m interfaces.banco --importar-json
python -m interfaces.agendador --fonte-produtos postgres --eventos console --uma-vez
```

A importação atualiza tipo/páginas dos endereços já cadastrados, preserva `ativo`
e não apaga os ausentes do JSON. Para acrescentar uma categoria pelo SQL Editor:

```sql
insert into public.produtos_monitorados (loja,url,tipo,paginas)
values ('kabum','https://www.kabum.com.br/hardware','listagem',2)
on conflict (loja,url) do nothing;
```

Uma categoria é um endereço de entrada; cada produto encontrado vira uma linha
individual de `ofertas` e novas linhas de histórico. Produtos coletados continuam
visíveis no catálogo mesmo se o endereço de entrada for desativado; a data informa
quando foram vistos pela última vez. O sistema ainda não marca produtos expirados.

Na pasta `web/`:

```bash
npm ci
npm run dev
```

Com CATALOG_SOURCE=postgres, o painel consulta ofertas e histórico (inclusive
produtos descobertos). O nome vem do coletor quando disponível; cupom sem percentual
mostra que o desconto não foi informado. Preço principal e histórico continuam
mostrando preço da página, e o preço calculado com cupom aparece separadamente.
Modo JSON mostra apenas links individuais e ignora entradas de categoria: ele
não tem acesso à memória do coletor. Requer servidor Node com Python instalado;
exportação estática/Edge não suporta este adaptador existente.

Modo local explícito, sem banco nem Redis:

```bash
# services/scraper
python -m interfaces.agendador --persistencia memoria --fonte-produtos json --eventos console --uma-vez
# web (outro terminal)
CATALOG_SOURCE=json npm run dev
```

Memória perde referência ao reiniciar; use PostgreSQL quando precisar preservá-la.
Falha no PostgreSQL encerra a coleta com erro, sem ativar memória silenciosamente.
A web mostra erro de leitura, sem trocar a fonte nem exibir credenciais.

## Escolher a entrega dos eventos

```bash
# Na pasta services/scraper
python -m interfaces.agendador --eventos console --uma-vez
python -m interfaces.agendador --eventos redis --uma-vez
python -m interfaces.agendador --eventos postgres --persistencia postgres --uma-vez
```

Redis continua disponível no docker-compose e é a única fila que o Go consome.
Com Redis, execute `docker compose up -d redis` na raiz e o notifier conforme seu
README. A opção console não envia nada; a opção postgres só grava avisos pendentes.
`--eventos postgres` exige persistência PostgreSQL e usa a mesma conexão/transação.
Um aviso contado como publicado nesse modo significa **enfileirado**, não enviado.

A referência inicial, o preço final anterior e `em_promocao` são recuperados antes
de cada coleta; carregar o banco não gera evento. O bloqueio por produto dura até
commit/rollback e também protege a primeira inserção contra coletores concorrentes.
O histórico registra cada observação, mesmo quando o preço não muda.

## Testes isolados

Na pasta `services/scraper`, `pytest -q` executa os testes locais; sem
TEST_DATABASE_URL, os seis testes de integração PostgreSQL ficam explicitamente
ignorados. Para testar armazenamento sem lojas ou serviços de mensagens, prepare
um PostgreSQL **local separado** (exemplo, ajuste usuário/porta):

```bash
createdb bot_promocoes_test
export TEST_DATABASE_URL='postgresql://usuario@localhost:5432/bot_promocoes_test?sslmode=disable'
pytest -q
```

O usuário de testes deve ter CREATEDB. O teste de permissões também exige CREATEROLE
(use o administrador desse PostgreSQL local). Cada teste cria um banco de nome
aleatório, aplica o SQL e remove **só esse banco** no final; nenhuma tabela existente
é truncada. Nunca aponte TEST_DATABASE_URL a um banco de produção ou ao Supabase real.
Os testes cobrem reinício, cupons conhecidos/desconhecidos/removidos, histórico,
produtos de categoria, rollback, concorrência, RLS e publicação console/Redis
(com cliente Redis simulado, sem enviar notificações).

Na pasta `web/`, usando o mesmo TEST_DATABASE_URL exportado:

```bash
export SCRAPER_PYTHON='../services/scraper/.venv/bin/python'
node --experimental-strip-types --test tests/*.test.mjs
npm run lint
npx tsc --noEmit
npm run build
```

Node 24 é usado nos testes. O teste web PostgreSQL cria outro banco descartável,
grava um produto pelo caso de uso Python e verifica sua leitura pelo adaptador web.
Sem TEST_DATABASE_URL, só essa parte é ignorada. O teste não visita lojas.

Banco local aprovado não comprova conexão Supabase: depois de configurar o projeto
real e aplicar o SQL, `python -m interfaces.banco` verifica essa conexão sem gravar
ofertas nem enviar mensagens. Uma coleta com `--eventos console` valida a gravação
real. Confira a contagem e a interface antes de ativar notificações.

## O que falta para substituir o Redis

Ainda é necessário implementar um adaptador no Go que leia `eventos_pendentes` e
reutilize o JSON de `payload` (contrato versão 2 de `docs/evento-promocao.md`).
Planejamento para esse consumidor, **não implementado nesta etapa**:

1. Numa transação curta, selecionar avisos não enviados, disponíveis e sem reserva
   válida com `FOR UPDATE SKIP LOCKED`; atualizar `reservado_ate`, `reserva_token`
   único e incrementar `tentativas`. Commit antes da chamada ao Telegram.
2. Enviar fora da transação. Usar reserva com validade e renovação se necessário,
   para dois processos não pegarem o mesmo aviso enquanto o envio está ativo.
3. Após sucesso, atualizar `enviado_em` apenas se o token da reserva ainda for seu.
   Após falha, registrar erro sanitizado e definir `disponivel_em` com espera
   crescente; liberar reserva. Limitar tentativas e oferecer revisão/reenvio manual.
4. Recuperar reservas expiradas após quedas, testar concorrência, falha de rede,
   timeouts, reinício e casos de resposta de envio desconhecida antes de desligar Redis.

A gravação de oferta + histórico + aviso é atômica somente no transporte PostgreSQL.
Redis/console não participam da transação do banco: pode haver publicação externa
seguida de falha no commit. Mesmo com a futura fila, uma queda após o Telegram
aceitar e antes da confirmação no banco pode levar a reenvio. **Não há promessa de
entrega sem duplicações.** A transição para a nova fila também precisa evitar rodar
os dois consumidores sobre os mesmos avisos e decidir como tratar pendências Redis.

## Estado desta entrega (03/11/2026)

- Pasta oficial: `/home/arthur/Documentos/bot_promocoes`, branch `develop`, sem
  alterações locais antes do trabalho. Não houve commit, push, merge ou PR.
- Projeto remoto identificado: **Bot_promocoes**, ref `fpjfvzsdbxaeepswzozc`,
  região `us-east-1`. O esquema `public` estava sem tabelas. A migração
  `integracao_coletor_postgres` foi aplicada pelo conector Supabase com o conteúdo
  de `sql/schema.sql`; **não execute o script novamente nesse projeto**.
- As quatro tabelas foram consultadas com sucesso no remoto (ainda vazias).
  RLS ativo e SELECT negado para anon/authenticated foram confirmados. O advisor
  retornou só quatro informações de RLS sem políticas, decisão intencional para
  acesso exclusivo do backend proprietário. Nenhum dado de teste foi inserido no remoto.
- **Ainda falta configurar a senha de banco em DATABASE_URL no `.env` privado.**
  A consulta pelo conector não comprova a conexão TCP/SSL do scraper ou da web.
  Copie a URL Session pooler do Connect desse projeto, depois rode
  `python -m interfaces.banco` e uma coleta `--eventos console` conforme acima.
- **107 testes Python passaram**, incluindo seis integrações com PostgreSQL 16
  local separado, sem serviços de mensagens. Os 95 testes anteriores permanecem
  aprovados. **3 testes web passaram**, incluindo a consulta dos dados gravados
  pelo caso de uso Python num banco descartável.
- ESLint e TypeScript passaram. O build `npx next build --webpack` passou fora do
  sandbox. `npm run build` (Turbopack) falhou neste ambiente ao tentar abrir uma
  porta para processar CSS, inclusive após a tentativa com permissão ampliada.
  A configuração existente do Next.js não foi alterada para contornar isso.
- Testes Go pendentes: executável `go` ausente no ambiente. O código Go e o Redis
  não foram alterados. Redis foi testado no Python com cliente simulado; conexão
  real Redis e envio Telegram não foram testados nesta etapa.
- `git diff --check` aprovado. Os arquivos novos aparecem como não rastreados em
  `git status`; use também esse comando na revisão, pois `git diff` comum mostra
  apenas os arquivos que já eram versionados.

## Revisão por arquivo (antes → depois)

Caminhos relativos à raiz; “novo” significa que o arquivo foi acrescentado.

| Arquivo | Antes → depois / motivo |
| --- | --- |
| `.env.example` | Exemplo genérico → escolhas independentes, URL Supabase com SSL e variáveis explicadas sem segredos. |
| `README.md` | Só título → entrada para configuração e documentação. |
| `sql/schema.sql` (novo) | Sem esquema versionado → tabelas, restrições, índices, RLS e revogação de acesso público. |
| `services/scraper/requirements.txt` | Sem driver SQL → psycopg fixado em 3.2.13; demais dependências preservadas. |
| `services/scraper/domain/repositorios.py` | Só buscar/salvar → contexto de transação opcional; memória continua funcionando. |
| `services/scraper/application/processar_coleta.py` | Salvamento e publicação separados → transação por produto e atualização do nome/link observados; regras de promoção preservadas. |
| `services/scraper/infrastructure/persistencia/postgres.py` (novo) | Só memória → recuperação integral da oferta, histórico por coleta e fonte de endereços no banco, com SSL e bloqueio concorrente. |
| `services/scraper/infrastructure/mensageria/postgres.py` (novo) | Redis/console → opção adicional de aviso pendente com o mesmo JSON, dentro da transação. |
| `services/scraper/interfaces/agendador.py` | Memória fixa e Redis escolhido pela presença de URL → opções separadas e explícitas, conexão fechada ao sair e falha sem fallback. |
| `services/scraper/interfaces/banco.py` (novo) | Sem verificação/importação → contagens somente leitura e importação explícita de endereços JSON, sem mensagens. |
| `services/scraper/tests/test_config_postgres.py` (novo) | Sem testes dessas opções → combinações inválidas, falta/falha de conexão e SSL remoto. |
| `services/scraper/tests/test_postgres.py` (novo) | Sem integração SQL → testes isolados de persistência, reinício, histórico, rollback, concorrência, fontes e permissões. |
| `web/lib/catalog/env.ts` (novo) | Raiz não carregada pela web → leitura do `.env` compartilhado, sem sobrescrever ambiente. |
| `web/lib/catalog.ts` | Fonte inferida só por URL → também aceita escolha explícita JSON/PostgreSQL e preserva erro sem fallback. |
| `web/lib/catalog/postgres-source.ts` | Catálogo partia dos endereços e inferia ID → parte de ofertas, usa ID/nome/cupom persistidos e inclui descobertas de categorias, com SSL remoto. |
| `web/lib/catalog/json-source.ts` | Categoria quebrava a conversão de URL → categorias ignoradas no catálogo local sem dados de coleta. |
| `web/lib/catalog/types.ts` | Sem dados de cupom → campos opcionais para código, percentual e preço final. |
| `web/components/catalog/product-card.tsx` | Sem cupom → mostra o código e o desconto/preço final quando conhecidos, preservando preço principal e layout. |
| `web/tests/catalog.test.mjs` | Só seleção implícita → cobre seleção explícita e JSON com categoria. |
| `web/tests/postgres.test.mjs` (novo) | Sem teste de produto descoberto → mapeamento de ID real e leitura real do banco preenchido pelo coletor. |
| `web/README.md` | Integração ainda descrita como ausente → configuração e comportamento atuais, incluindo o `.env` compartilhado. |
| `docs/supabase.md` (novo) | Sem guia integrado → configuração, execução, testes, limites e plano do futuro consumidor Go. |
