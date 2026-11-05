from psycopg.pq import TransactionStatus

from application.portas import PublicadorDeEventos
from domain.eventos import PromocaoDetectada
from infrastructure.mensageria.contrato import serializar_evento


class PublicadorPostgres(PublicadorDeEventos):
    def __init__(self, conexao):
        self.conexao = conexao

    def publicar(self, evento: PromocaoDetectada) -> None:
        # Impede uso acidental fora da transação de oferta + histórico.
        if self.conexao.info.transaction_status != TransactionStatus.INTRANS:
            raise RuntimeError("Fila PostgreSQL exige a transação do repositório PostgreSQL")
        self.conexao.execute(
            "INSERT INTO public.eventos_pendentes (payload) VALUES (%s::jsonb)",
            (serializar_evento(evento),),
        )
