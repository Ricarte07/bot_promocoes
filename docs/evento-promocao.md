# Contrato do evento `promocao_detectada`

Este é o único ponto de contato entre o scraper (Python) e o notifier (Go).
O scraper escreve, o notifier lê. Qualquer mudança aqui precisa ser feita nos
dois lados e na versão do evento.

## Transporte

- Redis Streams, stream `promocoes`.
- Cada entrada do stream tem um único campo, `json`, com o evento serializado.
- O notifier consome com um consumer group chamado `notifier`, para que a
  mensagem fique guardada se ele estiver fora do ar e seja entregue depois.

## Formato

```json
{
  "tipo": "promocao_detectada",
  "versao": 1,
  "produto_id": "8776497",
  "loja": "americanas",
  "nome": "Impressora Epson EcoTank L1250 Wi-Fi Bivolt",
  "url": "https://www.americanas.com.br/impressora-epson-ecotank-l1250-tanque-de-tinta-wi-fi-usb-8297500-8776497/p",
  "preco_atual": "901.55",
  "preco_referencia": "1099.90",
  "desconto_percentual": "18.04",
  "ocorrido_em": "2026-10-28T13:05:12.345678+00:00"
}
```

| Campo                 | Tipo   | Regra                                                        |
| --------------------- | ------ | ------------------------------------------------------------ |
| `tipo`                | string | Sempre `promocao_detectada`.                                 |
| `versao`              | int    | Versão deste contrato. Hoje `1`.                             |
| `produto_id`          | string | Id do produto na loja. Único junto com `loja`.               |
| `loja`                | string | Nome da loja em minúsculas: `kabum`, `americanas`.           |
| `nome`                | string | Nome do produto como a loja exibe. Pode vir vazio.           |
| `url`                 | string | Página do produto. Pode vir vazio.                           |
| `preco_atual`         | string | Decimal com 2 casas e ponto, em reais. Nunca float.          |
| `preco_referencia`    | string | Preço que serviu de base para o desconto. Mesmo formato.     |
| `desconto_percentual` | string | Decimal com 2 casas, em porcentagem.                         |
| `ocorrido_em`         | string | RFC 3339 em UTC, com fração de segundo e offset `+00:00`.    |

## Por que preços são strings

JSON só tem um tipo numérico, e a maioria dos parsers o lê como float.
`901.55` em float vira `901.5499999...`. Como string, o Python manda o
`Decimal` exato e o Go lê como `string` e converte com uma biblioteca
decimal, ou exibe direto na mensagem sem converter.

## Quem implementa

- Python: `services/scraper/infrastructure/mensageria/contrato.py`,
  função `serializar_evento`, com teste em `tests/test_contrato_evento.py`.
- Go: `services/notifier/internal/infrastructure/queue`, que decodifica o
  campo `json` para a struct do domínio.
