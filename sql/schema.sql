-- Execute somente após conferir o projeto e a ausência destas tabelas.
-- Sem IF NOT EXISTS: um esquema anterior incompatível deve falhar, não ser ignorado.
BEGIN;
CREATE TABLE public.produtos_monitorados (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loja text NOT NULL CHECK (loja <> ''),
    url text NOT NULL CHECK (url ~ '^https?://'),
    tipo text NOT NULL DEFAULT 'produto' CHECK (tipo IN ('produto', 'listagem')),
    paginas integer NOT NULL DEFAULT 1 CHECK (paginas > 0),
    ativo boolean NOT NULL DEFAULT true,
    categoria text,
    UNIQUE (loja, url)
);
-- Lista única das categorias: o menu do Telegram é montado a partir dela.
-- ofertas.categoria e produtos_monitorados.categoria não têm chave estrangeira:
-- uma categoria desconhecida no produtos.json vira só um aviso no log.
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
CREATE TABLE public.referencias_precos (
    loja text NOT NULL,
    produto_id text NOT NULL,
    preco_referencia numeric NOT NULL CHECK (preco_referencia > 0),
    PRIMARY KEY (loja, produto_id)
);
CREATE TABLE public.ofertas (
    loja text NOT NULL,
    produto_id text NOT NULL,
    nome text NOT NULL DEFAULT '',
    url text NOT NULL DEFAULT '',
    preco_referencia numeric NOT NULL CHECK (preco_referencia > 0),
    preco_atual numeric NOT NULL CHECK (preco_atual > 0),
    preco_de numeric CHECK (preco_de > 0),
    preco_final numeric NOT NULL CHECK (preco_final > 0),
    cupom_codigo text CHECK (cupom_codigo <> ''),
    cupom_desconto_percentual numeric CHECK (cupom_desconto_percentual > 0 AND cupom_desconto_percentual < 100),
    em_promocao boolean NOT NULL,
    -- A promoção aprovada pelas regras do bot: de onde vem o desconto e quanto ele é.
    base_desconto text CHECK (base_desconto IN ('referencia', 'menor_30_dias', 'preco_de_loja')),
    desconto_percentual numeric CHECK (desconto_percentual >= 0 AND desconto_percentual < 100),
    categoria text,
    atualizada_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (loja, produto_id),
    CHECK (cupom_codigo IS NOT NULL OR cupom_desconto_percentual IS NULL),
    CONSTRAINT ofertas_origem_so_em_promocao CHECK (base_desconto IS NULL OR em_promocao)
);
CREATE TABLE public.historico_precos (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loja text NOT NULL,
    produto_id text NOT NULL,
    preco numeric NOT NULL CHECK (preco > 0),
    preco_de numeric CHECK (preco_de > 0),
    preco_final numeric NOT NULL CHECK (preco_final > 0),
    cupom_codigo text,
    cupom_desconto_percentual numeric CHECK (cupom_desconto_percentual > 0 AND cupom_desconto_percentual < 100),
    coletado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (loja, produto_id) REFERENCES public.referencias_precos (loja, produto_id),
    CHECK (cupom_codigo IS NOT NULL OR cupom_desconto_percentual IS NULL)
);
CREATE INDEX historico_produto_data_idx ON public.historico_precos (loja, produto_id, coletado_em, id);
-- Outbox: o aviso é gravado junto da oferta; ainda não há consumidor Go desta fila.
CREATE TABLE public.eventos_pendentes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    criado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    disponivel_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    tentativas integer NOT NULL DEFAULT 0 CHECK (tentativas >= 0),
    reservado_ate timestamptz,
    reserva_token uuid,
    enviado_em timestamptz,
    ultimo_erro text
);
CREATE INDEX eventos_pendentes_disponiveis_idx ON public.eventos_pendentes (disponivel_em, id) WHERE enviado_em IS NULL;
ALTER TABLE public.produtos_monitorados ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ofertas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.referencias_precos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.historico_precos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eventos_pendentes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categorias ENABLE ROW LEVEL SECURITY;
-- Só o backend, conectado como proprietário, tem acesso. Nenhuma política pública.
REVOKE ALL ON public.produtos_monitorados, public.ofertas, public.referencias_precos, public.historico_precos, public.eventos_pendentes, public.categorias FROM PUBLIC;
REVOKE ALL ON SEQUENCE public.produtos_monitorados_id_seq, public.historico_precos_id_seq, public.eventos_pendentes_id_seq FROM PUBLIC;
-- Estes papéis existem no Supabase, mas não necessariamente no PostgreSQL local.
DO $$
DECLARE papel text;
BEGIN
    FOREACH papel IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
            EXECUTE format('REVOKE ALL ON public.produtos_monitorados, public.ofertas, public.referencias_precos, public.historico_precos, public.eventos_pendentes, public.categorias FROM %I', papel);
            EXECUTE format('REVOKE ALL ON SEQUENCE public.produtos_monitorados_id_seq, public.historico_precos_id_seq, public.eventos_pendentes_id_seq FROM %I', papel);
        END IF;
    END LOOP;
END $$;
COMMIT;
