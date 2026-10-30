import json
from datetime import datetime, timezone
from decimal import Decimal

from domain.cupom import Cupom
from domain.eventos import PromocaoDetectada
from infrastructure.mensageria.contrato import serializar_evento


def evento_exemplo(cupom=Cupom("ESQUENTA", Decimal("5"))):
    return PromocaoDetectada(
        produto_id="725571",
        loja="kabum",
        preco_atual=Decimal("279.99"),
        preco_referencia=Decimal("377.77"),
        desconto_percentual=Decimal("29.59"),
        nome="Fonte Gamer Rise Mode Elektra, 650W, Bronze, Full Modular",
        url="https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w",
        cupom=cupom,
        ocorrido_em=datetime(2026, 10, 30, 17, 54, 35, 380000, tzinfo=timezone.utc),
    )


def test_json_segue_o_contrato_documentado():
    texto = serializar_evento(evento_exemplo())

    assert json.loads(texto) == {
        "tipo": "promocao_detectada",
        "versao": 2,
        "produto_id": "725571",
        "loja": "kabum",
        "nome": "Fonte Gamer Rise Mode Elektra, 650W, Bronze, Full Modular",
        "url": "https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w",
        "preco_atual": "279.99",
        "preco_final": "265.99",
        "preco_referencia": "377.77",
        "desconto_percentual": "29.59",
        "cupom": {"codigo": "ESQUENTA", "desconto_percentual": "5.00"},
        "ocorrido_em": "2026-10-30T17:54:35.380000+00:00",
    }


def test_sem_cupom_o_campo_vai_nulo_e_preco_final_igual_ao_atual():
    dados = json.loads(serializar_evento(evento_exemplo(cupom=None)))

    assert dados["cupom"] is None
    assert dados["preco_final"] == dados["preco_atual"] == "279.99"


def test_cupom_sem_valor_conhecido_vai_com_percentual_nulo():
    dados = json.loads(serializar_evento(evento_exemplo(cupom=Cupom("10DO10"))))

    assert dados["cupom"] == {"codigo": "10DO10", "desconto_percentual": None}
    assert dados["preco_final"] == "279.99"


def test_precos_sao_texto_com_duas_casas_e_nunca_float():
    texto = serializar_evento(evento_exemplo())

    assert '"preco_atual": "279.99"' in texto
    assert '"preco_referencia": "377.77"' in texto
    assert 279.99 not in json.loads(texto).values()


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
