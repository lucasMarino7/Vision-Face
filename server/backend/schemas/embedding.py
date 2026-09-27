"""Schemas de serialização e desserialização da tabela ``embedding``."""

from backend.models.embedding import EmbeddingModel
from backend.server.extensions import ma
from marshmallow import fields, validate


class EmbeddingSchema(ma.SQLAlchemyAutoSchema):
    """Representação de uma embedding facial associada a uma pessoa."""
    embedding = fields.List(
        fields.Float(),
        required=True,
        validate=validate.Length(equal=512)
    )

    class Meta:
        model = EmbeddingModel
        load_instance = True
        include_fk = True

        # Campos somente leitura, não permitir alter os valores desses campos
        dump_only = (
            'id',
            'created_at'
        )
