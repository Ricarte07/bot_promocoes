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
    UNIQUE (loja, url)
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
    atualizada_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (loja, produto_id),
    CHECK (cupom_codigo IS NOT NULL OR cupom_desconto_percentual IS NULL)
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
    FOREIGN KEY (loja, produto_id) REFERENCES public.ofertas (loja, produto_id),
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
ALTER TABLE public.historico_precos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eventos_pendentes ENABLE ROW LEVEL SECURITY;
-- Só o backend, conectado como proprietário, tem acesso. Nenhuma política pública.
REVOKE ALL ON public.produtos_monitorados, public.ofertas, public.historico_precos, public.eventos_pendentes FROM PUBLIC;
REVOKE ALL ON SEQUENCE public.produtos_monitorados_id_seq, public.historico_precos_id_seq, public.eventos_pendentes_id_seq FROM PUBLIC;
-- Estes papéis existem no Supabase, mas não necessariamente no PostgreSQL local.
DO $$
DECLARE papel text;
BEGIN
    FOREACH papel IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
            EXECUTE format('REVOKE ALL ON public.produtos_monitorados, public.ofertas, public.historico_precos, public.eventos_pendentes FROM %I', papel);
            EXECUTE format('REVOKE ALL ON SEQUENCE public.produtos_monitorados_id_seq, public.historico_precos_id_seq, public.eventos_pendentes_id_seq FROM %I', papel);
        END IF;
    END LOOP;
END $$;
COMMIT;
