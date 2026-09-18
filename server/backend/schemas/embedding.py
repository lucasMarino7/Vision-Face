"""Schemas de serialização e desserialização da tabela ``embedding``."""

from models.embedding import EmbeddingModel
from server.extensions import ma


class EmbeddingSchema(ma.SQLAlchemyAutoSchema):
    """Representação de uma embedding facial associada a uma pessoa."""

    class Meta:
        model = EmbeddingModel
        load_instance = True
        include_fk = True
