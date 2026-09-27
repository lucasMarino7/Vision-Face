from backend.models.sync_change import SyncChangeModel
from backend.server.extensions import ma


class SyncChangeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = SyncChangeModel
        load_instance = True

        # Campos somente leitura
        dump_only = (
            'id',
            'created_at'
        )
