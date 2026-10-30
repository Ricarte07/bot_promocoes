# notifier

Lê as promoções que o scraper publica no Redis e manda para o Telegram.

```
Redis Stream `promocoes`  ->  queue.Consumidor  ->  NotificarPromocao  ->  telegram.Cliente
```

- `internal/domain`: o que é uma promoção para o notifier.
- `internal/application`: caso de uso e as duas portas, fonte de promoções e notificador.
- `internal/infrastructure/queue`: consumidor do Redis Streams e decodificação do contrato
  de `docs/evento-promocao.md`.
- `internal/infrastructure/telegram`: envio pela Bot API com `net/http`.
- `cmd/notifier`: lê a configuração e liga as peças.

## Configurar o Telegram

1. No Telegram, fale com o `@BotFather`, mande `/newbot` e siga as perguntas.
   Ele devolve o token, algo como `123456789:AAH...`. Esse é o `TELEGRAM_BOT_TOKEN`.
2. Abra uma conversa com o bot recém-criado e mande qualquer mensagem.
3. No navegador, abra `https://api.telegram.org/bot<TOKEN>/getUpdates`, trocando
   `<TOKEN>` pelo token. Na resposta, o campo `"chat":{"id":...}` é o
   `TELEGRAM_CHAT_ID`. Para um grupo ou canal, adicione o bot nele antes e o id
   vem negativo.
4. Copie `.env.example` para `.env` na raiz do projeto e preencha os dois valores.

## Rodar

Dentro de `services/notifier`:

```bash
go test ./...                  # testes, sem precisar de Redis nem de Telegram
go run ./cmd/notifier -testar  # manda uma mensagem de teste e sai
go run ./cmd/notifier          # consome o stream até Ctrl+C
```

O Redis vem do `docker-compose.yml` na raiz: `docker compose up -d`.

## Comportamento em falhas

- Mensagem fora do contrato é descartada com aviso no log, para não travar as seguintes.
- Se o Telegram falhar, a mensagem fica pendente no Redis e é reentregue na
  próxima vez que o notifier subir.
- O consumer group é criado a partir das mensagens novas: promoções publicadas
  antes do primeiro `go run` não são enviadas.
