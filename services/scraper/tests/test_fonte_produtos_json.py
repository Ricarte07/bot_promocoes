import pytest

from application.portas import ProdutoMonitorado
from infrastructure.persistencia.produtos_json import (
    ArquivoDeProdutosInvalido,
    FonteDeProdutosJson,
)


def escrever(tmp_path, conteudo: str):
    arquivo = tmp_path / "produtos.json"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def test_le_lista_de_produtos(tmp_path):
    arquivo = escrever(
        tmp_path,
        '[{"loja": "kabum", "url": "https://www.kabum.com.br/produto/1/a"},'
        ' {"loja": "kabum", "url": "https://www.kabum.com.br/produto/2/b"}]',
    )

    produtos = FonteDeProdutosJson(arquivo).listar()

    assert produtos == [
        ProdutoMonitorado("kabum", "https://www.kabum.com.br/produto/1/a"),
        ProdutoMonitorado("kabum", "https://www.kabum.com.br/produto/2/b"),
    ]


def test_lista_vazia_e_valida(tmp_path):
    assert FonteDeProdutosJson(escrever(tmp_path, "[]")).listar() == []


def test_json_mal_formado(tmp_path):
    with pytest.raises(ArquivoDeProdutosInvalido):
        FonteDeProdutosJson(escrever(tmp_path, "[{isso nao e json")).listar()


def test_item_sem_url_e_invalido(tmp_path):
    with pytest.raises(ArquivoDeProdutosInvalido):
        FonteDeProdutosJson(escrever(tmp_path, '[{"loja": "kabum"}]')).listar()


def test_raiz_que_nao_e_lista_e_invalida(tmp_path):
    with pytest.raises(ArquivoDeProdutosInvalido):
        FonteDeProdutosJson(escrever(tmp_path, '{"loja": "kabum", "url": "x"}')).listar()


def test_le_listagem_com_paginas(tmp_path):
    arquivo = escrever(
        tmp_path,
        '[{"loja": "kabum", "listagem": "https://www.kabum.com.br/hardware/placa-de-video-vga", "paginas": 2},'
        ' {"loja": "kabum", "listagem": "https://www.kabum.com.br/hardware/fontes"}]',
    )

    produtos = FonteDeProdutosJson(arquivo).listar()

    assert produtos == [
        ProdutoMonitorado("kabum", "https://www.kabum.com.br/hardware/placa-de-video-vga", tipo="listagem", paginas=2),
        ProdutoMonitorado("kabum", "https://www.kabum.com.br/hardware/fontes", tipo="listagem", paginas=1),
    ]


def test_paginas_invalidas_e_erro(tmp_path):
    with pytest.raises(ArquivoDeProdutosInvalido):
        FonteDeProdutosJson(escrever(tmp_path, '[{"loja": "kabum", "listagem": "x", "paginas": 0}]')).listar()
    with pytest.raises(ArquivoDeProdutosInvalido):
        FonteDeProdutosJson(escrever(tmp_path, '[{"loja": "kabum", "listagem": "x", "paginas": "2"}]')).listar()


def test_item_sem_url_nem_listagem_e_invalido(tmp_path):
    with pytest.raises(ArquivoDeProdutosInvalido):
        FonteDeProdutosJson(escrever(tmp_path, '[{"loja": "kabum", "paginas": 2}]')).listar()


# --- categoria -------------------------------------------------------------


def test_le_a_categoria_de_produto_e_de_listagem(tmp_path):
    arquivo = escrever(
        tmp_path,
        '[{"loja": "kabum", "url": "https://www.kabum.com.br/produto/1/a", "categoria": "fontes"},'
        ' {"loja": "kabum", "listagem": "https://www.kabum.com.br/gamer/consoles",'
        '  "paginas": 2, "categoria": "consoles"}]',
    )

    produto, listagem = FonteDeProdutosJson(arquivo).listar()

    assert produto.categoria == "fontes"
    assert listagem.categoria == "consoles"
    assert listagem.paginas == 2


def test_item_sem_categoria_fica_com_categoria_vazia(tmp_path):
    arquivo = escrever(tmp_path, '[{"loja": "kabum", "url": "https://www.kabum.com.br/produto/1/a"}]')

    assert FonteDeProdutosJson(arquivo).listar()[0].categoria is None


@pytest.mark.parametrize("categoria", ['"Placas de Vídeo"', '""', '7', '"placas_de_video"'])
def test_categoria_fora_do_formato_e_recusada(tmp_path, categoria):
    arquivo = escrever(
        tmp_path,
        f'[{{"loja": "kabum", "url": "https://www.kabum.com.br/produto/1/a", "categoria": {categoria}}}]',
    )

    with pytest.raises(ArquivoDeProdutosInvalido, match="categoria"):
        FonteDeProdutosJson(arquivo).listar()


def test_o_produtos_json_do_projeto_tem_categoria_em_todos_os_itens():
    from interfaces.composicao import ARQUIVO_PADRAO

    produtos = FonteDeProdutosJson(ARQUIVO_PADRAO).listar()

    assert produtos
    assert [p.url for p in produtos if not p.categoria] == []
