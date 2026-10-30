# Contrato do evento `promocao_detectada`

Este é o único ponto de contato entre o scraper (Python) e o notifier (Go).
O scraper escreve, o notifier lê. Qualquer mudança aqui precisa ser feita nos
dois lados e na versão do evento.

## Transporte

- Redis Streams, stream `promocoes`.
- Cada entrada do stream tem um único campo, `json`, com o evento serializado.
- O notifier consome com um consumer group chamado `notifier`, para que a
  mensagem fique guardada se ele estiver fora do ar e seja entregue depois.

## Formato (versão 2)

```json
{
  "tipo": "promocao_detectada",
  "versao": 2,
  "produto_id": "725571",
  "loja": "kabum",
  "nome": "Fonte Gamer Rise Mode Elektra, 650W, Bronze, Full Modular",
  "url": "https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w",
  "preco_atual": "279.99",
  "preco_final": "265.99",
  "preco_referencia": "377.77",
  "desconto_percentual": "29.59",
  "cupom": {"codigo": "ESQUENTA", "desconto_percentual": "5.00"},
  "ocorrido_em": "2026-10-30T17:54:35.380000+00:00"
}
```

| Campo                 | Tipo           | Regra                                                                 |
| --------------------- | -------------- | --------------------------------------------------------------------- |
| `tipo`                | string         | Sempre `promocao_detectada`.                                          |
| `versao`              | int            | Versão deste contrato. Hoje `2`.                                      |
| `produto_id`          | string         | Id do produto na loja. Único junto com `loja`.                        |
| `loja`                | string         | Nome da loja em minúsculas: `kabum`, `americanas`.                    |
| `nome`                | string         | Nome do produto como a loja exibe. Pode vir vazio.                    |
| `url`                 | string         | Página do produto. Pode vir vazio.                                    |
| `preco_atual`         | string         | Preço "por" mostrado na página, sem cupom. Decimal com 2 casas.       |
| `preco_final`         | string         | O que o comprador paga: `preco_atual` com o cupom aplicado. Igual a `preco_atual` quando não há cupom ou o valor dele é desconhecido. |
| `preco_referencia`    | string         | Base do desconto: o preço "de" anunciado pela loja ou o primeiro preço que o scraper viu, o que der o maior desconto. |
| `desconto_percentual` | string         | Desconto de `preco_final` sobre `preco_referencia`, 2 casas.          |
| `cupom`               | objeto ou null | Cupom anunciado na página. `codigo` em maiúsculas; `desconto_percentual` em 2 casas, ou `null` quando a loja não informa o valor. |
| `ocorrido_em`         | string         | RFC 3339 em UTC, com fração de segundo e offset `+00:00`.             |

## Mudanças por versão

- **2**: `preco_final` e `cupom`. `preco_referencia` passou a poder ser o
  preço "de" da loja, não só o primeiro preço visto.
- **1**: formato inicial.

## Por que preços são strings

JSON só tem um tipo numérico, e a maioria dos parsers o lê como float.
`901.55` em float vira `901.5499999...`. Como string, o Python manda o
`Decimal` exato e o Go lê como `string` e exibe direto na mensagem.

## Quem implementa

- Python: `services/scraper/infrastructure/mensageria/contrato.py`,
  função `serializar_evento`, com teste em `tests/test_contrato_evento.py`.
- Go: `services/notifier/internal/infrastructure/queue/evento.go`, que
  decodifica o campo `json` para a struct do domínio.
