-- Aplique uma vez em bancos criados com o esquema anterior, com o scraper parado.
BEGIN;
CREATE TABLE public.referencias_precos (
    loja text NOT NULL,
    produto_id text NOT NULL,
    preco_referencia numeric NOT NULL CHECK (preco_referencia > 0),
    PRIMARY KEY (loja, produto_id)
);

INSERT INTO public.referencias_precos (loja, produto_id, preco_referencia)
SELECT loja, produto_id, preco_referencia FROM public.ofertas;

ALTER TABLE public.historico_precos
    DROP CONSTRAINT historico_precos_loja_produto_id_fkey,
    ADD CONSTRAINT historico_precos_referencia_fk FOREIGN KEY (loja, produto_id)
        REFERENCES public.referencias_precos (loja, produto_id);

ALTER TABLE public.referencias_precos ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.referencias_precos FROM PUBLIC;
DO $$
DECLARE papel text;
BEGIN
    FOREACH papel IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
            EXECUTE format('REVOKE ALL ON public.referencias_precos FROM %I', papel);
        END IF;
    END LOOP;
END $$;
COMMIT;
