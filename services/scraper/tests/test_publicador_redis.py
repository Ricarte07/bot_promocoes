import json
from decimal import Decimal

from domain.eventos import PromocaoDetectada
from infrastructure.mensageria.redis_streams import PublicadorRedis


class RedisFalso:
    """Guarda as chamadas de xadd em vez de falar com um servidor."""

    def __init__(self):
        self.entradas: list[tuple[str, dict, int | None, bool]] = []

    def xadd(self, name, fields, maxlen=None, approximate=False):
        self.entradas.append((name, fields, maxlen, approximate))
        return f"1761656712345-{len(self.entradas) - 1}"


def evento():
    return PromocaoDetectada(
        produto_id="415807",
        loja="kabum",
        preco_atual=Decimal("1569.99"),
        preco_referencia=Decimal("1964.59"),
        desconto_percentual=Decimal("20.09"),
        nome="Water Cooler NZXT Kraken Elite 240 RGB",
        url="https://www.kabum.com.br/produto/415807/water-cooler-nzxt",
    )


def test_publica_uma_entrada_no_stream_promocoes_com_campo_json():
    redis = RedisFalso()

    PublicadorRedis(redis).publicar(evento())

    assert len(redis.entradas) == 1
    stream, campos, _, _ = redis.entradas[0]
    assert stream == "promocoes"
    assert list(campos) == ["json"]
    dados = json.loads(campos["json"])
    assert dados["tipo"] == "promocao_detectada"
    assert dados["produto_id"] == "415807"
    assert dados["preco_atual"] == "1569.99"


def test_limita_o_tamanho_do_stream_de_forma_aproximada():
    redis = RedisFalso()

    PublicadorRedis(redis, tamanho_maximo=500).publicar(evento())

    _, _, maxlen, approximate = redis.entradas[0]
    assert maxlen == 500
    assert approximate is True


def test_stream_pode_ser_trocado():
    redis = RedisFalso()

    PublicadorRedis(redis, stream="promocoes-teste").publicar(evento())

    assert redis.entradas[0][0] == "promocoes-teste"
