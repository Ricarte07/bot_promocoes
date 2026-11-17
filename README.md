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

## Começando

```bash
cp .env.example .env              # preencha a senha do banco e, se for usar, o Telegram
docker compose up -d postgres redis
```

O banco oficial é o Postgres do Docker; o Supabase fica para testes compartilhados.
Configuração, comandos sem envio de mensagens, testes com banco e o plano da futura
fila PostgreSQL estão em [docs/banco.md](docs/banco.md).
