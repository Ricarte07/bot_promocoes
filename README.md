# Monitoramento automático de promoções

**projeto em desenvolvimento:** este readme descreve a proposta. não significa que os recursos já estejam decididos.

## A ideia

a gente escolhe as categorias, cadastra fontes autorizadas e define regras para identificar ofertas interessantes. o sistema coleta os dados periodicamente, guarda o histórico e envia as notificações. um dashboard ajuda a analisar tudo.

## Stack e bibliotecas principais

a stack base está definida. as bibliotecas e outras ferramentas vão ser depois

| parte            | tecnologia  | para que usar                                                |
| ---------------- | ----------- | ------------------------------------------------------------ |
| coleta e análise | python      | consultar fontes, organizar os dados e aplicar as regras de promoção. |
| telegram         | go (golang) | cuidar da integração com o telegram e do envio das notificações. |
| dashboard        | next.js     | exibir as ofertas, o histórico e a situação das coletas.     |
| armazenamento    | postgresql  | guardar produtos, preços, fontes, coletas e alertas.         |



## Arquitetura

o python cuida dos dados no geral ; o golang cuida da integração com o telegram; o next.js vai exibir os dados pelo frontend. o postgresql conecta esse fluxo.

no mvp, o proprio banco pode guardar uma lista de alertas pendentes. assim, não precisamos começar com uma fila externa. o dashboard acessa o banco somente no servidor

## Como o fluxo deve funcionar

1. ler o json e validar categorias, fontes e regras.
2. consultar as fontes habilitadas, respeitando os limites de cada uma.
3. padronizar produto, categoria, loja, preço, moeda, link e horário da coleta.
4. salvar o histórico e comparar ofertas do mesmo produto e condição de compra.
5. aplicar as regras e criar alertas pendentes, evitando repetições.
6. o serviço go envia os avisos no telegram
7. o dashboard permite acompanhar ofertas, histórico e problemas de coleta.

## Configuração em JSON

exemplo ilustrativo de formato — ainda não é um contrato implementado:

```json
{
  "categorias": ["monitores", "perifericos"],
  "intervalo_coleta_minutos": 30,
  "fontes_habilitadas": [],
  "regras": {
    "queda_minima_percentual": 10,
  }
}
```

as categorias e os valores são tudo exemplos. as fontes vão ser cadastradas depois de confirmar a autorização e as condições de acesso.



