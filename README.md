# bot_promocoes

Coletor Python de promoções, notificações Go via Redis e interface Next.js.

A configuração PostgreSQL/Supabase, comandos de execução, testes sem envio de
mensagens e o plano para a futura fila PostgreSQL estão em
[docs/supabase.md](docs/supabase.md). Comece pelo `.env.example` e por `sql/schema.sql`.

O Redis permanece disponível. A fila PostgreSQL ainda não tem consumidor Go.
