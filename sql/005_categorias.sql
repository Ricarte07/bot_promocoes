-- Aplique uma vez em bancos criados antes desta versão do schema, ANTES de ligar
-- o scraper com o código que grava a categoria (ele falha sem as colunas novas).
-- Só cria a tabela de categorias e acrescenta colunas vazias: pode rodar com o
-- bot ligado. Na rodada seguinte o scraper preenche a categoria de cada oferta.
--
-- Rode no SQL Editor do Supabase (ou no psql do Postgres local).
BEGIN;

-- Lista única das categorias: o menu do Telegram é montado a partir dela, e o
-- scraper avisa no log quando o produtos.json usa uma categoria que não está aqui.
CREATE TABLE public.categorias (
    slug text PRIMARY KEY CHECK (slug ~ '^[a-z0-9-]+$'),
    nome text NOT NULL CHECK (nome <> ''),
    ordem integer NOT NULL,
    ativa boolean NOT NULL DEFAULT true
);

INSERT INTO public.categorias (slug, nome, ordem) VALUES
    ('placas-de-video', 'Placas de vídeo', 10),
    ('processadores', 'Processadores', 20),
    ('placas-mae', 'Placas-mãe', 30),
    ('coolers', 'Coolers', 40),
    ('fontes', 'Fontes', 50),
    ('monitores', 'Monitores', 60),
    ('perifericos', 'Periféricos', 70),
    ('controles', 'Controles', 80),
    ('impressoras', 'Impressoras', 90),
    ('consoles', 'Consoles e jogos', 100),
    ('notebooks', 'Notebooks', 110),
    ('pcs-montados', 'PCs montados', 120);

-- Sem chave estrangeira de propósito: uma categoria desconhecida no produtos.json
-- vira só um aviso no log, nunca uma rodada perdida.
ALTER TABLE public.ofertas ADD COLUMN categoria text;
ALTER TABLE public.produtos_monitorados ADD COLUMN categoria text;

ALTER TABLE public.categorias ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.categorias FROM PUBLIC;
DO $$
DECLARE papel text;
BEGIN
    FOREACH papel IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
            EXECUTE format('REVOKE ALL ON public.categorias FROM %I', papel);
        END IF;
    END LOOP;
END $$;

COMMIT;
