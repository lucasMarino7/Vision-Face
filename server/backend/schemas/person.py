"""Schemas de serialização e desserialização da tabela ``person``."""

from backend.models.person import PersonModel
from backend.server.extensions import ma
from .embedding import EmbeddingSchema


class PersonSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PersonModel
        load_instance = True
        include_relationships = True

        # Campos somente leitura, não permite alterar estes valores
        dump_only = (
            'id',
            'created_at'
        )

    # dump_only=True significa que o campo será apenas para saída, não para entrada
    embeddings = ma.Nested(EmbeddingSchema, many=True, dump_only=True)
