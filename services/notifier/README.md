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
5. Opcional: `TELEGRAM_INTERVALO_SEGUNDOS` define a pausa mínima entre duas
   mensagens, em segundos. O padrão, 1.1, é o limite do Telegram para o mesmo
   chat; valores maiores espaçam as notificações, e as que ainda não saíram
   ficam guardadas no Redis enquanto esperam.

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
- Se o Telegram falhar, a mensagem fica pendente no Redis e é tentada de novo
  depois de 1 minuto, sem precisar reiniciar o notifier. Na partida, o que ficou
  pendente da execução anterior é tentado antes das novas; uma pendente que
  continua falhando não trava a leitura das seguintes.
- A mesma promoção (loja, produto, preço final e cupom) não é enviada duas vezes
  em 7 dias, mesmo que o evento chegue repetido. Isso fica num Decorator
  (`application.NotificadorIdempotente`) em volta do cliente do Telegram, com as
  chaves `enviado:*` no Redis. Se o preço cair ou o cupom mudar, é outra promoção.
- O consumer group é criado a partir das mensagens novas: promoções publicadas
  antes do primeiro `go run` não são enviadas.
