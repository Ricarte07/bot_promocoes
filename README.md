# Bufos Promo (bot_promocoes)

Bot que acompanha preços na Kabum e na Americanas, decide o que é promoção de
verdade e avisa num chat do Telegram. Um painel web mostra as promoções, o motivo de
cada uma e o histórico de preços.

## Como funciona

```
Kabum / Americanas
      │  a cada rodada (hoje, 10 min): listagens de categoria e, quando o preço mudou, a página do produto
      ▼
scraper (Python) ── decide se é promoção ──► Supabase (Postgres: ofertas e histórico)
      │                                            ▲
      │ promoção nova                              │ só leitura
      ▼                                            │
Redis (fila) ──► notifier (Go) ──► Telegram     painel web (Next.js, na Vercel)
```

**O que é promoção** (regras em `services/scraper/domain/regras_promocao.py`):

- desconto de pelo menos **15%** sobre o preço final (já com cupom, quando a loja
  informa o percentual);
- a base do desconto é a **queda vista pelo próprio bot** (o primeiro preço visto) ou o
  preço **"de"** que a loja anuncia;
- o "de" da loja só vale se o preço atual for o **menor que o bot viu em 30 dias**. Com
  menos de 7 dias de histórico, ele é aceito e marcado como "informado pela loja, não
  conferido";
- o desconto fixo do Pix não conta como promoção.

Cada promoção guarda a **origem** (queda vista pelo bot, menor preço em 30 dias ou "de"
da loja), que aparece no Telegram e no painel. O notifier não repete a mesma promoção
(mesmo produto, preço final e cupom) por 7 dias.

## Estrutura

```
services/
├── scraper/    Python  · coleta preços e decide promoções (DDD: domain, application, infrastructure, interfaces)
├── notifier/   Go      · lê as promoções do Redis e envia ao Telegram (cmd, internal)
└── web/        Next.js · painel: promoções, filtros, origem do desconto e histórico
sql/            schema.sql (banco do zero) e migrações numeradas
docs/           banco, contrato do evento e publicação do painel
iniciar-bot.ps1 sobe o bot inteiro nesta máquina
```

Cada serviço tem um README com como rodar e testar.

## Rodando

1. `.env` na raiz, a partir do [`.env.example`](.env.example). Ele nunca vai para o Git.
2. Docker Desktop aberto (para o Redis).
3. Na raiz:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\iniciar-bot.ps1 -ComPainel
   ```

   Abre o scraper, o notifier e o painel (http://localhost:3000), cada um numa janela.
   O script recusa subir um segundo bot por cima do primeiro.

Deixe o notebook sem suspender enquanto o bot roda. Se o banco derrubar a conexão, a
rodada falha e a seguinte reconecta sozinha.

## Onde ficam as coisas

| O quê | Onde |
| --- | --- |
| Banco oficial | Supabase, projeto "Promo Bufos" (São Paulo). Detalhes em [docs/banco.md](docs/banco.md) |
| Fila de promoções | Redis no Docker do notebook |
| Painel publicado | Vercel. Passo a passo em [docs/deploy-vercel.md](docs/deploy-vercel.md) |
| Contrato scraper → notifier | [docs/evento-promocao.md](docs/evento-promocao.md) |
| Testes | `pytest` (scraper), `go test` (notifier), `node --test` (painel); todos no CI do GitHub |

## Limitações conhecidas

- **O bot roda no notebook.** Se ele desligar, o bot para. O próximo passo é um
  servidor (uma VM da empresa ou uma VPS) com o `docker compose` subindo tudo.
- **Americanas:** só a primeira página de cada categoria (12 produtos). O site entrega
  as páginas seguintes por uma API própria, ainda não estudada.
- **Pix na Kabum:** o desconto é calculado sobre o preço no Pix. Comparado com o
  preço no cartão, cerca de 10% das promoções ficariam abaixo de 15%.
- **Rodada:** ~5 a 7 minutos com o banco no Supabase (o banco fica a ~55 ms por ida e
  volta). Depois de muito tempo parado, a primeira rodada demora mais, porque confere na
  página cada produto que mudou.
