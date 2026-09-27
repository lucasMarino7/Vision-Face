from flask_restx import Resource, fields, Namespace, reqparse, inputs
from flask import request, jsonify, current_app
from backend.models.sync_change import *
from backend.models.embedding import *
from backend.models.person import *
from backend.schemas.embedding import *
from backend.schemas.person import *
from backend.schemas.sync_change import *


sync_ns = Namespace(
    name='sync', description='Operations related to synchronization of data between the client and the server.')

# parser utilizado para validar os parametros de paginação da rota
full_sync_parser = reqparse.RequestParser()
full_sync_parser.add_argument(
    'offset',
    type=inputs.int_range(0, 1000000),  # Mínimo 0
    default=0,
    required=False,
    help='Índice de início da paginação (deve ser >= 0)'
)
full_sync_parser.add_argument(
    'limit',
    type=inputs.int_range(1, 500),  # Entre 1 e 500
    default=500,
    required=False,
    help='Quantidade de registros a retornar (entre 1 e 500)'
)

# schemas
embedding_schema = EmbeddingSchema()
embedding_list_schema = EmbeddingSchema(many=True)

person_schema = PersonSchema()
person_list_schema = PersonSchema(many=True)

sync_change_schema = SyncChangeSchema()
sync_change_list_schema = SyncChangeSchema(many=True)


class SyncUtils:
    TABLE_MAP = {
        "embeddings": {
            "model": EmbeddingModel,
            "schema": embedding_list_schema,
            "max_id_attr": "embedded_max_id",
        },
        "persons": {
            "model": PersonModel,
            "schema": person_list_schema,
            "max_id_attr": "people_max_id",
        },
    }

    @classmethod
    def get_full_sync_data(cls, table_name: str, snapshot_version: int, offset: int, limit: int) -> tuple[dict | None, int]:
        """
            Retorna os dados de sincronização completa (full sync) para a versão do snapshot especificada.
        """
        table_config = cls.TABLE_MAP.get(table_name)
        if not table_config:
            current_app.logger.warning(
                f"Tentativa de consulta com tabela inválida: '{table_name}' (offset={offset}, limit={limit})"
            )
            return {"message": f"Tabela '{table_name}' é inválida."}, 400

        # O snapshot é buscado apenas uma vez aqui
        snapshot = cls.get_snapshot_by_version(snapshot_version)
        if snapshot is None:
            return {"message": "Versão do snapshot inexistente."}, 404

        model = table_config["model"]
        schema = table_config["schema"]
        max_id = getattr(snapshot, table_config["max_id_attr"])

        # obtendo os registros do banco de dados, filtrando pelo offset e limit
        # e ordenando crescente pelo id, e limitando a quantidade de registros retornados pelo limit + 1, para saber se existe mais registros para retornar.
        # o limit + 1 é necessário para saber se existe mais registros para retornar, pois se o limit for 500 e existirem 501 registros, o limit + 1 irá retornar 501 registros, e assim podemos saber que existe mais registros para retornar.
        records = (
            model.query
            .filter(
                model.id > offset,
                model.id <= max_id
            )
            .order_by(model.id.asc())
            .limit(limit + 1)
            .all()
        )

        # verifica se existe mais registros para retornar, comparando a quantidade de registros retornados com o limit.
        has_more = len(records) > limit
        if has_more:
            # remove o ultimo registro retornado, pois ele é apenas para verificar se existe mais registros para retornar.
            records = records[:limit]

        # define o next_offset como o id do ultimo registro retornado, ou o offset atual caso não existam registros retornados.
        next_offset = records[-1].id if records else offset

        items = schema.dump(records)

        return {
            "snapshot_version": snapshot_version,
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset,
            "has_more": has_more,
            "count": len(items),
            "items": items
        }, 200


@sync_ns.route('/status')
class SyncStatusResource(Resource):
    @sync_ns.response(200, 'Get the latest snapshot version.')
    def get(self):
        """
            Retorna a versão do snapshot mais recente.
        """
        latest_snapshot = SyncChangeModel.get_last_snapshot()
        if latest_snapshot is None:
            return {'latest_snapshot_version': 0}, 200

        return {
            'latest_snapshot_version': latest_snapshot.version,
            'people_max_id': latest_snapshot.people_max_id,
            'embedded_max_id': latest_snapshot.embedded_max_id
        }, 200


@sync_ns.route('/delta/<int:from_version>')
class DeltaSyncResource(Resource):
    @sync_ns.response(200, 'Alterações processadas com sucesso (mesmo se vazia).')
    def get(self, from_version):
        """
        Retorna todas as alterações ocorridas após a versão informada.
        Exemplo:
            GET /api/sync/delta/1586
        Retorna alterações com:
            version > 1586
        """

        changes = SyncChangeModel.get_changes_after_version(from_version)

        if not changes:
            return {
                'message': 'No changes available.',
                'from_version': from_version,
                'count': 0,
                'items': []
            }, 200

        return {
            'from_version': from_version,
            'to_version': changes[-1].version,
            'count': len(changes),
            'items': sync_change_list_schema.dump(changes)
        }, 200


# Rota única que substitui FullSyncEmbeddingsResource e FullSyncPersonsResource
@sync_ns.route("/full/<int:version>/<string:table_name>")
class FullSyncResource(Resource):
    @sync_ns.doc(
        params={
            'version': {
                'description': 'Versão do snapshot para sincronização completa',
                'type': 'integer',
                'example': 1586
            },
            'table_name': {
                'description': 'Nome da tabela que deseja sincronizar',
                'type': 'string',
                # Gera um dropdown no Swagger UI
                'enum': ['embeddings', 'persons'],
                'example': 'embeddings'
            }
        },
        responses={
            200: 'Dados de sincronização obtidos com sucesso',
            400: 'Parâmetro inválido (offset, limit ou table_name)',
            404: 'Versão do snapshot não encontrada'
        }
    )
    @sync_ns.expect(full_sync_parser)
    def get(self, version: int, table_name: str):
        """
        Retorna sincronização completa dinamicamente para embeddings ou persons.
        """
        # usa o parser criado para validar os parametros de offset e limit
        args = full_sync_parser.parse_args()

        response_data, status_code = SyncUtils.get_full_sync_data(
            table_name=table_name,
            snapshot_version=version,
            offset=args['offset'],
            limit=args['limit']
        )

        return response_data, status_code
