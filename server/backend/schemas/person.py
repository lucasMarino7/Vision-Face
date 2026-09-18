"""Schemas de serialização e desserialização da tabela ``person``."""

from models.person import PersonModel
from server.extensions import ma
from embedding import EmbeddingSchema


class PersonSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PersonModel
        load_instance = True
        include_relationships = True

    # dump_only=True significa que o campo será apenas para saída, não para entrada
    embeddings = ma.Nested(EmbeddingSchema, many=True, dump_only=True)
