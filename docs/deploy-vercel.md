# Publicar o painel na Vercel

O painel (`services/web`) é um site Next.js que só lê o banco. Na Vercel ele roda sem
servidor ligado: cada acesso abre uma conexão rápida com o Supabase, lê as ofertas e o
histórico e fecha. O bot (scraper e notifier) continua rodando onde está hoje; a Vercel
publica só o painel.

## Antes de começar

- **Usuário só-leitura do Supabase** (`sql/003_painel_somente_leitura.sql`) já criado e
  com senha. O painel publicado usa só ele: nunca coloque na Vercel a `DATABASE_URL` do
  scraper, que pode escrever no banco.
- **Plano:** o plano gratuito (Hobby) da Vercel é para uso pessoal e não comercial. Para
  um projeto da empresa, confirme com o responsável se vale o plano Pro.
- **Acesso:** o endereço de produção fica aberto para quem tiver o link (decisão de
  25/11/2026). Os dados são só de leitura e a senha do banco fica no servidor, nunca vai
  para o navegador.

## Passo a passo

1. Em **vercel.com**, entre com a conta do GitHub e clique em **Add New… → Project**.
2. Em **Import Git Repository**, escolha `bot_promocoes`. Se ele não aparecer, autorize o
   app da Vercel a ler esse repositório no GitHub.
3. Na tela de configuração:
   - **Root Directory:** `services/web` (clique em *Edit* e escolha a pasta);
   - **Framework Preset:** Next.js (a Vercel detecta sozinha);
   - **Build e Output:** deixe o padrão.
4. Em **Environment Variables**, cadastre:

   | Nome | Valor |
   | --- | --- |
   | `CATALOG_SOURCE` | `postgres` |
   | `PANEL_DATABASE_URL` | a URL do **Session pooler** com o usuário só-leitura: `postgresql://painel_leitura.<id do projeto>:<senha>@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require` |

   A mesma linha que está no `.env` da raiz serve. Cole direto na Vercel, sem mandar a
   senha por chat ou e-mail.
5. Clique em **Deploy**. Leva uns 2 minutos.
6. Depois do primeiro deploy, em **Settings → Functions → Function Region**, escolha
   **São Paulo, Brazil (gru1)**: o banco está em São Paulo, e com a função lá cada
   acesso fica bem mais rápido. Salve e faça **Redeploy** para valer.

## Conferir

- Abra o endereço que a Vercel mostrar (algo como `bot-promocoes.vercel.app`).
- O cartão "Promoções do bot" deve mostrar o mesmo número do painel local.
- Se aparecer "Não foi possível carregar os produtos", confira a `PANEL_DATABASE_URL`
  (usuário `painel_leitura.<id>`, senha, `?sslmode=require` no fim) e veja o erro em
  **Deployments → (o deploy) → Logs**.

## Depois de publicado

- Cada merge na branch de produção da Vercel (a branch padrão do repositório) publica
  sozinho uma versão nova. PRs ganham um endereço de prévia, protegido por login da
  Vercel por padrão.
- Trocar a senha do usuário só-leitura exige atualizar a `PANEL_DATABASE_URL` na Vercel
  e fazer *Redeploy*.
