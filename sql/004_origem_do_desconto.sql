-- Aplique uma vez em bancos criados antes desta versão do schema.
-- Só acrescenta colunas vazias: pode rodar com o scraper ligado. Na rodada
-- seguinte o scraper preenche a origem e o desconto de cada promoção.
BEGIN;
ALTER TABLE public.ofertas
    ADD COLUMN base_desconto text
        CHECK (base_desconto IN ('referencia', 'menor_30_dias', 'preco_de_loja')),
    ADD COLUMN desconto_percentual numeric
        CHECK (desconto_percentual >= 0 AND desconto_percentual < 100),
    ADD CONSTRAINT ofertas_origem_so_em_promocao
        CHECK (base_desconto IS NULL OR em_promocao);
COMMIT;
