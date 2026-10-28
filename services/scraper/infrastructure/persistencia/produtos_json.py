"""Adaptador da porta FonteDeProdutosMonitorados que lê um arquivo JSON.

Formato esperado do arquivo:
[
  {"loja": "kabum", "url": "https://www.kabum.com.br/produto/415807/..."},
  {"loja": "americanas", "url": "https://www.americanas.com.br/impressora-epson-...-8776497/p"},
  ...
]
"""

import json
from pathlib import Path

from application.portas import FonteDeProdutosMonitorados, ProdutoMonitorado


class ArquivoDeProdutosInvalido(ValueError):
    """O arquivo existe, mas não tem o formato esperado."""


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
            if not isinstance(item, dict) or not item.get("loja") or not item.get("url"):
                raise ArquivoDeProdutosInvalido(
                    f"{self.caminho}: item {posicao} precisa ter 'loja' e 'url'"
                )
            produtos.append(ProdutoMonitorado(loja=str(item["loja"]), url=str(item["url"])))

        return produtos
