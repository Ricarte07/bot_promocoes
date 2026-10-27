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
