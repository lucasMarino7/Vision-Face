from datetime import datetime
from backend.server.extensions import db
from sqlalchemy import asc, desc


class SyncChangeModel(db.Model):
    """Contém informações sobre as alterações do banco de dados, criando versionamento."""

    __tablename__ = "sync_change"

    version = db.Column(db.Integer(), primary_key=True)
    table_name = db.Column(db.String(100), nullable=False)
    register_id = db.Column(db.Integer(), nullable=False)
    # inserção, atualização ou exclusão
    operation = db.Column(db.String(10), nullable=False)

    # Armaenando o maior id de cada tabela para que quando fazer sincronização full irá retornar os registros até o maior id de cada tabela
    people_max_id = db.Column(db.Integer(), nullable=True)
    embedded_max_id = db.Column(db.Integer(), nullable=True)

    created_at = db.Column(db.DateTime(), nullable=False,
                           default=datetime.utcnow)

    def __init__(self, table_name, register_id, operation, people_max_id=None, embedded_max_id=None) -> None:
        self.table_name = table_name
        self.register_id = register_id
        self.operation = operation
        self.people_max_id = people_max_id
        self.embedded_max_id = embedded_max_id

    @classmethod
    def find_by_version(cls, version) -> "SyncChangeModel":
        return cls.query.filter_by(version=version).first()

    @classmethod
    def find_by_table_name(cls, table_name) -> list["SyncChangeModel"]:
        return cls.query.filter_by(table_name=table_name).all()

    @classmethod
    def find_all(cls) -> list["SyncChangeModel"]:
        return cls.query.all()

    @classmethod
    def get_last_snapshot(cls) -> "SyncChangeModel":
        return cls.query.order_by(cls.version.desc()).first()

    @classmethod
    def get_changes_after_version(cls, from_version: int, order: str = "asc") -> list["SyncChangeModel"]:
        """
        Retorna as alterações após uma determinada versão com ordenação dinâmica (asc/desc).
        """
        # Trata o parâmetro para ignorar maiúsculas/minúsculas e espaços
        normalized_order = order.lower().strip() if isinstance(order, str) else "asc"

        # Define a direção da ordenação com base no parâmetro
        order_clause = desc(
            cls.version) if normalized_order == "desc" else asc(cls.version)

        return (
            cls.query
            .filter(
                cls.version > from_version
            )
            .order_by(
                order_clause
            )
            .all()
        )

    def save_to_db(self) -> None:
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self) -> None:
        db.session.delete(self)
        db.session.commit()
