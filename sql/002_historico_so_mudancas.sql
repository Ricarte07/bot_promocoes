-- Opcional. Compacta o histórico gravado antes de o scraper passar a guardar só
-- mudanças: apaga cada linha igual à anterior do mesmo produto (preço, "de",
-- preço final e cupom), mantendo a primeira de cada sequência. O resultado é o
-- mesmo histórico que o código novo teria gravado; nenhuma mudança de preço se
-- perde, só as repetições. A última visita de cada produto continua em
-- ofertas.atualizada_em.
--
-- Rode com o scraper parado. A contagem do fim mostra quantas linhas ficaram.
BEGIN;

DELETE FROM public.historico_precos h
USING (
    SELECT id,
           row(preco, preco_de, preco_final, cupom_codigo, cupom_desconto_percentual)
             IS NOT DISTINCT FROM
           lag(row(preco, preco_de, preco_final, cupom_codigo, cupom_desconto_percentual))
             OVER (PARTITION BY loja, produto_id ORDER BY coletado_em, id) AS repetida
    FROM public.historico_precos
) r
WHERE h.id = r.id AND r.repetida;

SELECT count(*) AS linhas_no_historico FROM public.historico_precos;

COMMIT;
