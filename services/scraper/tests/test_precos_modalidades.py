"""Preços da página são evidência; modalidades ausentes não são presumidas."""

import json
from decimal import Decimal

import pytest

from domain.cupom import Cupom
from domain.oferta import Oferta
from domain.preco import Preco
from infrastructure.scrapers.base import PaginaInvalida
from infrastructure.scrapers.kabum import extrair_produto as extrair_kabum
from infrastructure.scrapers.americanas import extrair_produto as extrair_americanas


def pagina_kabum(produto):
    dados = {'props': {'pageProps': {'product': produto}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(dados)}</script>'


def test_kabum_separa_avista_original_e_cupom_sem_somar_descontos():
    produto = extrair_kabum(pagina_kabum({
        'id': 1, 'title': 'Placa', 'available': True, 'price': 3000,
        'prices': {'priceWithDiscount': 2400, 'oldPrice': 3000},
        'stamps': {'title': 'CUPOM DEZ', 'description': 'Use o cupom DEZ e ganhe 10% OFF'},
    }))
    assert produto.preco_avista == Decimal('2400')
    assert produto.preco_de == Decimal('3000')
    assert produto.cupom == Cupom('DEZ', Decimal('10'))
    oferta = Oferta('1', 'kabum', Preco(Decimal('3000')))
    oferta.registrar_preco(Preco(produto.preco_avista), produto.cupom, Preco(produto.preco_de))
    assert oferta.preco_final.valor == Decimal('2160.00')
    assert len(oferta.coletar_eventos()) == 1


def test_kabum_sem_preco_confirmavel_falha():
    with pytest.raises(PaginaInvalida, match='preço'):
        extrair_kabum(pagina_kabum({'id': 1, 'available': True, 'prices': {}}))


def test_americanas_escolhe_vendedor_em_estoque_sem_inferir_pix():
    produto = extrair_americanas('''<script type="application/ld+json">
    {"@type":"Product","sku":"1","name":"Impressora","offers":[
      {"price":"1250","availability":"https://schema.org/InStock","seller":{"name":"A"}},
      {"price":"1100","availability":"https://schema.org/InStock","seller":{"name":"B"}},
      {"price":"900","availability":"https://schema.org/OutOfStock","seller":{"name":"C"}}
    ]}</script>''')
    assert produto.preco_avista == Decimal('1100')
    assert produto.vendedor == 'B'
    assert produto.cupom is None
    assert produto.preco_de is None
