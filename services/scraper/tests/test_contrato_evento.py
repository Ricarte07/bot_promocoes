import json
from datetime import datetime, timezone
from decimal import Decimal

from domain.eventos import PromocaoDetectada
from infrastructure.mensageria.contrato import serializar_evento


def evento_exemplo():
    return PromocaoDetectada(
        produto_id="8776497",
        loja="americanas",
        preco_atual=Decimal("901.55"),
        preco_referencia=Decimal("1099.9"),
        desconto_percentual=Decimal("18.04"),
        nome="Impressora Epson EcoTank L1250 Wi-Fi Bivolt",
        url="https://www.americanas.com.br/impressora-epson-8776497/p",
        ocorrido_em=datetime(2026, 10, 28, 13, 5, 12, 345678, tzinfo=timezone.utc),
    )


def test_json_segue_o_contrato_documentado():
    texto = serializar_evento(evento_exemplo())

    assert json.loads(texto) == {
        "tipo": "promocao_detectada",
        "versao": 1,
        "produto_id": "8776497",
        "loja": "americanas",
        "nome": "Impressora Epson EcoTank L1250 Wi-Fi Bivolt",
        "url": "https://www.americanas.com.br/impressora-epson-8776497/p",
        "preco_atual": "901.55",
        "preco_referencia": "1099.90",
        "desconto_percentual": "18.04",
        "ocorrido_em": "2026-10-28T13:05:12.345678+00:00",
    }


def test_precos_sao_texto_com_duas_casas_e_nunca_float():
    texto = serializar_evento(evento_exemplo())

    assert '"preco_atual": "901.55"' in texto
    assert '"preco_referencia": "1099.90"' in texto
    assert 901.55 not in json.loads(texto).values()


def test_acentos_saem_legiveis_e_nao_escapados():
    evento = PromocaoDetectada(
        produto_id="1",
        loja="kabum",
        preco_atual=Decimal("800"),
        preco_referencia=Decimal("1000"),
        desconto_percentual=Decimal("20.00"),
        nome="Placa de Vídeo",
    )

    assert '"nome": "Placa de Vídeo"' in serializar_evento(evento)
