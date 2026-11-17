# bot_promocoes

Coletor Python de promoções, notificações Go via Redis e interface Next.js.

## Estrutura

```
services/
├── scraper/    Python  · coleta preços e detecta promoções (domain, application, infrastructure, interfaces)
├── notifier/   Go      · lê as promoções do Redis e envia ao Telegram (cmd, internal)
└── web/        Next.js · painel com catálogo, filtros e histórico de preços
sql/            esquema do banco (schema.sql)
docs/           contrato do evento e guia do banco
```

Cada serviço tem seu próprio README com como rodar e testar.

A configuração PostgreSQL/Supabase, comandos de execução, testes sem envio de
mensagens e o plano para a futura fila PostgreSQL estão em
[docs/supabase.md](docs/supabase.md). Comece pelo `.env.example` e por `sql/schema.sql`.

O Redis permanece disponível. A fila PostgreSQL ainda não tem consumidor Go.
