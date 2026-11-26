"""Adaptador da porta FonteDeProdutosMonitorados que lê um arquivo JSON.

Formato esperado do arquivo:
[
  {"loja": "kabum", "url": "https://www.kabum.com.br/produto/415807/...", "categoria": "coolers"},
  {"loja": "americanas", "url": "https://www.americanas.com.br/impressora-epson-...-8776497/p"},
  {"loja": "kabum", "listagem": "https://www.kabum.com.br/hardware/placa-de-video-vga", "paginas": 2,
   "categoria": "placas-de-video"},
  ...
]

"url" aponta para um produto. "listagem" aponta para uma página de categoria,
e todos os produtos dela são monitorados; "paginas" (opcional, padrão 1) diz
quantas páginas da listagem seguir. "categoria" (opcional) é o slug da tabela
categorias que os produtos vistos ali recebem: só letras minúsculas, números e
hífen, como "placas-de-video".
"""

import json
import re
from pathlib import Path

from application.portas import (
    TIPO_LISTAGEM,
    TIPO_PRODUTO,
    FonteDeProdutosMonitorados,
    ProdutoMonitorado,
)


class ArquivoDeProdutosInvalido(ValueError):
    """O arquivo existe, mas não tem o formato esperado."""


_FORMATO_CATEGORIA = re.compile(r"[a-z0-9-]+")


class FonteDeProdutosJson(FonteDeProdutosMonitorados):
    def __init__(self, caminho: Path | str):
        self.caminho = Path(caminho)

    def listar(self) -> list[ProdutoMonitorado]:
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            raise ArquivoDeProdutosInvalido(f"{self.caminho}: JSON mal formado ({erro})")

        if not isinstance(dados, list):
            raise ArquivoDeProdutosInvalido(f"{self.caminho}: esperava uma lista de produtos")

        produtos = []
        for posicao, item in enumerate(dados):
            produtos.append(self._ler_item(posicao, item))

        return produtos

    def _ler_item(self, posicao: int, item) -> ProdutoMonitorado:
        if not isinstance(item, dict) or not item.get("loja"):
            raise ArquivoDeProdutosInvalido(f"{self.caminho}: item {posicao} precisa ter 'loja'")

        categoria = self._ler_categoria(posicao, item)

        if item.get("url"):
            return ProdutoMonitorado(loja=str(item["loja"]), url=str(item["url"]), categoria=categoria)

        if item.get("listagem"):
            paginas = item.get("paginas", 1)
            if not isinstance(paginas, int) or paginas < 1:
                raise ArquivoDeProdutosInvalido(
                    f"{self.caminho}: item {posicao}: 'paginas' precisa ser inteiro maior que zero"
                )
            return ProdutoMonitorado(
                loja=str(item["loja"]), url=str(item["listagem"]), tipo=TIPO_LISTAGEM, paginas=paginas,
                categoria=categoria,
            )

        raise ArquivoDeProdutosInvalido(
            f"{self.caminho}: item {posicao} precisa ter 'url' (produto) ou 'listagem'"
        )

    def _ler_categoria(self, posicao: int, item: dict) -> str | None:
        categoria = item.get("categoria")
        if categoria is None:
            return None
        if not isinstance(categoria, str) or not _FORMATO_CATEGORIA.fullmatch(categoria):
            raise ArquivoDeProdutosInvalido(
                f"{self.caminho}: item {posicao}: 'categoria' precisa ser um slug como "
                f"'placas-de-video' (letras minúsculas, números e hífen)"
            )
        return categoria
