"""Verificação somente leitura e importação explícita dos endereços JSON; não envia avisos."""

import argparse
import os

from interfaces.agendador import ARQUIVO_PADRAO, ENV_PADRAO, carregar_dotenv
from infrastructure.persistencia.postgres import conectar
from infrastructure.persistencia.produtos_json import FonteDeProdutosJson


def main():
    carregar_dotenv(ENV_PADRAO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--importar-json', action='store_true')
    parser.add_argument('--produtos', default=ARQUIVO_PADRAO)
    opcoes = parser.parse_args()
    with conectar(os.environ.get('DATABASE_URL', '')) as conexao:
        if opcoes.importar_json:
            with conexao.transaction():
                for produto in FonteDeProdutosJson(opcoes.produtos).listar():
                    conexao.execute(
                        """INSERT INTO public.produtos_monitorados (loja,url,tipo,paginas)
                        VALUES (%s,%s,%s,%s) ON CONFLICT (loja,url) DO UPDATE
                        SET tipo=EXCLUDED.tipo,paginas=EXCLUDED.paginas""",
                        (produto.loja, produto.url, produto.tipo, produto.paginas),
                    )
        # Consultas fixas; nenhuma credencial ou payload é exibido.
        for tabela in ('produtos_monitorados', 'ofertas', 'historico_precos', 'eventos_pendentes'):
            from psycopg import sql
            total = conexao.execute(sql.SQL('SELECT count(*) AS total FROM public.{}').format(
                sql.Identifier(tabela))).fetchone()['total']
            print(f'{tabela}: {total}')
        print('Conexão PostgreSQL e tabelas verificadas. Nenhum aviso enviado.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Verificação falhou: confira DATABASE_URL, SSL, permissões e sql/schema.sql. Nenhuma credencial foi exibida.') from None
