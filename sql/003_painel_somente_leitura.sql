-- Opcional, recomendado: usuário só-leitura para o painel web.
--
-- Hoje o painel usa a DATABASE_URL do scraper, que pode escrever no banco; o
-- "só leitura" dele é só uma opção da sessão. Com este usuário, o banco recusa
-- qualquer escrita vinda do painel, mesmo que alguém desligue essa opção.
--
-- Rode uma vez no SQL Editor do Supabase (ou no psql do Postgres local),
-- trocando TROQUE_ESTA_SENHA por uma senha forte, só com letras e números.
-- Depois, no .env da raiz, aponte PANEL_DATABASE_URL para este usuário (no
-- Supabase, pelo Session pooler o usuário fica painel_leitura.<id do projeto>).
BEGIN;

CREATE ROLE painel_leitura LOGIN PASSWORD 'TROQUE_ESTA_SENHA';
ALTER ROLE painel_leitura SET default_transaction_read_only = on;

GRANT USAGE ON SCHEMA public TO painel_leitura;
GRANT SELECT ON public.ofertas, public.historico_precos TO painel_leitura;

-- As tabelas têm RLS ligado e nenhuma política pública: sem estas duas
-- políticas, o usuário enxergaria as tabelas vazias.
CREATE POLICY painel_le_ofertas ON public.ofertas
    FOR SELECT TO painel_leitura USING (true);
CREATE POLICY painel_le_historico ON public.historico_precos
    FOR SELECT TO painel_leitura USING (true);

COMMIT;
