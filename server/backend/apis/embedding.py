from flask_restx import Resource, fields, Namespace
from backend.models.embedding import EmbeddingModel
from backend.models.person import PersonModel
from backend.schemas.embedding import EmbeddingSchema
from backend.server.extensions import db
from backend.models.sync_change import SyncChangeModel
from flask import request

embedding_ns = Namespace(name='embedding', description='Embedding operations')

embedding_schema = EmbeddingSchema()
embedding_list_schema = EmbeddingSchema(many=True)

embedding_input_model = embedding_ns.model('Create an embedding for a person', {
    'embedding': fields.List(
        fields.Float,
        required=True,
        min_items=512,  # o vetor deve conter 512 valores
        max_items=512,
        description='Face embedding vector with 512 values.'
    ),
    'model': fields.String(
        required=True,
        max_length=20,
        description='Name of the model used to generate the embedding.'
    ),
    'angle': fields.String(
        required=True,
        max_length=20,
        description='Face angle used to generate the embedding.'
    )
})

EMBEDDING_NOT_FOUND = 'Embedding not found.'
PERSON_NOT_FOUND = 'Person not found.'


def _create_embedding_sync_change(embedding_data, operation):
    # cria um novo registro na tabela de sync_change quando for feito uma operação na tabela de embedding
    # o flush envia as alterações feita na tabela embedding como update/delete/insert, mas sem encerrar a transação
    db.session.flush()

    return SyncChangeModel(
        table_name=EmbeddingModel.__tablename__,
        register_id=embedding_data.id,
        operation=operation,
        people_max_id=db.session.query(
            db.func.max(PersonModel.id)
        ).scalar(),
        embedded_max_id=db.session.query(
            db.func.max(EmbeddingModel.id)
        ).scalar()
    )


@embedding_ns.route('/<int:person_id>/embeddings')
class PersonEmbedding(Resource):
    @embedding_ns.response(200, 'Get all embeddings of the person.')
    @embedding_ns.response(404, PERSON_NOT_FOUND)
    def get(self, person_id):
        person_data = PersonModel.find_by_id(person_id)
        if person_data is None:
            return {'message': PERSON_NOT_FOUND}, 404

        embeddings = EmbeddingModel.query.filter_by(person_id=person_id).all()
        return embedding_list_schema.dump(embeddings), 200

    @embedding_ns.expect(embedding_input_model, validate=True)
    @embedding_ns.response(201, 'Create an embedding for a person.')
    @embedding_ns.response(404, PERSON_NOT_FOUND)
    def post(self, person_id):
        embedding_json = request.get_json()

        with db.session.begin():
            person_data = PersonModel.find_by_id(person_id)
            if person_data is None:
                return {'message': PERSON_NOT_FOUND}, 404

            embedding_data = embedding_schema.load({
                **embedding_json,
                'person_id': person_data.id,
                'dimension': len(embedding_json['embedding'])
            })
            db.session.add(embedding_data)
            db.session.add(
                _create_embedding_sync_change(embedding_data, 'insert')
            )

        return embedding_schema.dump(embedding_data), 201


@embedding_ns.route('/<int:person_id>/embeddings/<int:embedding_id>')
class PersonEmbeddingItem(Resource):
    @embedding_ns.expect(embedding_input_model, validate=True)
    @embedding_ns.response(200, 'Update an embedding of a person.')
    @embedding_ns.response(404, PERSON_NOT_FOUND)
    @embedding_ns.response(404, EMBEDDING_NOT_FOUND)
    def put(self, person_id, embedding_id):
        embedding_json = request.get_json()

        with db.session.begin():
            person_data = PersonModel.find_by_id(person_id)
            if person_data is None:
                return {'message': PERSON_NOT_FOUND}, 404

            embedding_data = EmbeddingModel.query.filter_by(
                id=embedding_id,
                person_id=person_id
            ).first()
            if embedding_data is None:
                return {'message': EMBEDDING_NOT_FOUND}, 404

            # faz atualização parcial no registro da embedding apenas atualizando aquilo que foi passado no json
            embedding_schema.load(
                {
                    **embedding_json,
                    'dimension': len(embedding_json['embedding'])
                },
                instance=embedding_data,
                partial=True
            )

            db.session.add(
                _create_embedding_sync_change(embedding_data, 'update')
            )

        return embedding_schema.dump(embedding_data), 200

    @embedding_ns.response(204, 'Delete an embedding of a person.')
    @embedding_ns.response(404, PERSON_NOT_FOUND)
    @embedding_ns.response(404, EMBEDDING_NOT_FOUND)
    def delete(self, person_id, embedding_id):
        with db.session.begin():
            person_data = PersonModel.find_by_id(person_id)
            if person_data is None:
                return {'message': PERSON_NOT_FOUND}, 404

            embedding_data = EmbeddingModel.query.filter_by(
                id=embedding_id,
                person_id=person_id
            ).first()
            if embedding_data is None:
                return {'message': EMBEDDING_NOT_FOUND}, 404

            db.session.delete(embedding_data)
            db.session.add(
                _create_embedding_sync_change(embedding_data, 'delete')
            )

        return '', 204


@embedding_ns.route('/')
class EmbeddingList(Resource):
    @embedding_ns.response(200, 'Get all embeddings.')
    def get(self):
        return embedding_list_schema.dump(EmbeddingModel.find_all()), 200
