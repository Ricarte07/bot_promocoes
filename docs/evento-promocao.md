# Contrato do evento `promocao_detectada`

Este é o único ponto de contato entre o scraper (Python) e o notifier (Go).
O scraper escreve, o notifier lê. Qualquer mudança aqui precisa ser feita nos
dois lados e na versão do evento.

## Transporte

- Redis Streams, stream `promocoes`.
- Cada entrada do stream tem um único campo, `json`, com o evento serializado.
- O notifier consome com um consumer group chamado `notifier`, para que a
  mensagem fique guardada se ele estiver fora do ar e seja entregue depois.

## Formato (versão 4)

```json
{
  "tipo": "promocao_detectada",
  "versao": 4,
  "produto_id": "725571",
  "loja": "kabum",
  "nome": "Fonte Gamer Rise Mode Elektra, 650W, Bronze, Full Modular",
  "url": "https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w",
  "preco_atual": "279.99",
  "preco_final": "265.99",
  "preco_referencia": "377.77",
  "desconto_percentual": "29.59",
  "cupom": {"codigo": "ESQUENTA", "desconto_percentual": "5.00"},
  "base_desconto": "menor_30_dias",
  "categoria": "fontes",
  "ocorrido_em": "2026-10-30T17:54:35.380000+00:00"
}
```

| Campo                 | Tipo           | Regra                                                                 |
| --------------------- | -------------- | --------------------------------------------------------------------- |
| `tipo`                | string         | Sempre `promocao_detectada`.                                          |
| `versao`              | int            | Versão deste contrato. Hoje `4`; o notifier ainda aceita a `2` e a `3`. |
| `produto_id`          | string         | Id do produto na loja. Único junto com `loja`.                        |
| `loja`                | string         | Nome da loja em minúsculas: `kabum`, `americanas`.                    |
| `nome`                | string         | Nome do produto como a loja exibe. Pode vir vazio.                    |
| `url`                 | string         | Página do produto. Pode vir vazio.                                    |
| `preco_atual`         | string         | Preço "por" mostrado na página, sem cupom. Decimal com 2 casas.       |
| `preco_final`         | string         | O que o comprador paga: `preco_atual` com o cupom aplicado. Igual a `preco_atual` quando não há cupom ou o valor dele é desconhecido. |
| `preco_referencia`    | string         | Base do desconto: o preço "de" anunciado pela loja ou o primeiro preço que o scraper viu, o que der o maior desconto entre as bases aprovadas pelas regras. |
| `desconto_percentual` | string         | Desconto de `preco_final` sobre `preco_referencia`, 2 casas.          |
| `cupom`               | objeto ou null | Cupom anunciado na página. `codigo` em maiúsculas; `desconto_percentual` em 2 casas, ou `null` quando a loja não informa o valor. |
| `base_desconto`       | string ou null | De onde vem o desconto: `referencia` (o bot viu o preço cair), `menor_30_dias` (o "de" da loja conferido: o preço é o menor que o bot viu em 30 dias) ou `preco_de_loja` (o "de" da loja, com menos de 7 dias de histórico para conferir). `null` quando não se sabe. |
| `categoria`           | string ou null | Slug da tabela `categorias` (ex.: `placas-de-video`, `consoles`), vindo do `produtos.json` (ou de `produtos_monitorados`) onde o produto foi visto por último. `null` quando o endereço não tem categoria. |
| `ocorrido_em`         | string         | RFC 3339 em UTC, com fração de segundo e offset `+00:00`.             |

## Mudanças por versão
- **4**: `categoria`. Serve para mandar a promoção só a quem escolheu aquela
  categoria no Telegram. O notifier aceita 2, 3 e 4: eventos antigos chegam sem
  categoria.
- **3**: `base_desconto`. Um "de" da loja que fica acima do menor preço visto
  pelo bot nos últimos 30 dias deixa de ser promoção (regras em
  `services/scraper/domain/regras_promocao.py`). O notifier aceita 2 e 3: um
  evento v2 sai sem a linha de origem.
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
