from flask_restx import Resource, fields, Namespace
from backend.models.person import *
from backend.models.embedding import EmbeddingModel
from backend.models.sync_change import SyncChangeModel
from backend.schemas.person import *

from flask import request, jsonify
from backend.server.extensions import db

person_ns = Namespace(name='person', description='People operations')


person_schema = PersonSchema()
person_list_schema = PersonSchema(many=True)


person_model = person_ns.model('Create / Update a person', {
    'name': fields.String(
        required=True,
        max_length=100,
        description='Full name of the person.'
    ),
    'date_birth': fields.Date(
        required=True,
        description='Date of birth of the person.'
    ),
    'wanted': fields.Boolean(
        required=True,
        description='Indicates whether the person is wanted.'
    ),
    'reason': fields.String(
        required=False,
        max_length=200,
        description='Reason why the person is wanted.'
    )
})

embedding_input_model = person_ns.model('Create an embedding for a person', {
    'embedding': fields.List(
        fields.Float,
        required=True,
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

PERSON_NOT_FOUND = 'Person not found.'


# cria um novo registro na tabela de sync_change quando for feito uma operação na tabela de person
# a operação na tabela de person e o novo registro na tabela de sync_change é atualizado no banco de dados de forma atomica dentro de uma mesma transação
def _create_person_sync_change(person_data, operation):
    # o flush envia as alterações feita na tabela person como update/delete/insert, mas sem encerrar a transação
    db.session.flush()

    return SyncChangeModel(
        table_name=PersonModel.__tablename__,
        register_id=person_data.id,
        operation=operation,
        people_max_id=db.session.query(
            db.func.max(PersonModel.id)
        ).scalar(),
        embedded_max_id=db.session.query(
            db.func.max(EmbeddingModel.id)
        ).scalar()
    )


@person_ns.route('/<int:person_id>')
class Person(Resource):
    @person_ns.response(200, 'Get an person.')
    def get(self, person_id):
        person_data = PersonModel.find_by_id(person_id)
        if person_data is None:
            return {'message': PERSON_NOT_FOUND}, 404

        return person_schema.dump(person_data), 200

    @person_ns.expect(person_model)
    @person_ns.response(200, 'Update a person.')
    def put(self, person_id):
        person_json = request.get_json()

        # alteração atomica em uma mesma transação fazer duas operações evitando dupla escrita/commit
        # após sair do 'with' é feito o commit
        with db.session.begin():
            person_data = PersonModel.find_by_id(person_id)
            if person_data is None:
                return {'message': PERSON_NOT_FOUND}, 404

            # Atualiza apenas as colunas que tiveram dados enviados.
            person_schema.load(
                person_json,
                instance=person_data,
                partial=True
            )
            db.session.add(_create_person_sync_change(person_data, 'update'))

        return person_schema.dump(person_data), 200

    @person_ns.response(204, 'Delete a person.')
    def delete(self, person_id):
        # alteração atomica em uma mesma transação fazer duas operações evitando dupla escrita/commit
        # após sair do 'with' é feito o commit
        with db.session.begin():
            person_data = PersonModel.find_by_id(person_id)
            if person_data is None:
                return {'message': PERSON_NOT_FOUND}, 404

            db.session.delete(person_data)
            db.session.add(_create_person_sync_change(person_data, 'delete'))
        return '', 204


@person_ns.route('/')
class PersonList(Resource):
    @person_ns.response(200, 'Get all the people.')
    def get(self):
        return person_list_schema.dump(PersonModel.find_all()), 200

    @person_ns.expect(person_model)
    @person_ns.response(201, 'Create a person.')
    def post(self):
        person_json = request.get_json()
        person_data = person_schema.load(person_json)

        # alteração atomica em uma mesma transação fazer duas operações evitando dupla escrita/commit
        # após sair do 'with' é feito o commit
        with db.session.begin():
            db.session.add(person_data)
            db.session.add(
                _create_person_sync_change(person_data, 'insert')
            )

        return person_schema.dump(person_data), 201
