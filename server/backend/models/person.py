from datetime import datetime
from backend.server.extensions import db


class PersonModel(db.Model):
    """Pessoa cadastrada para reconhecimento facial."""

    __tablename__ = "person"

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date_birth = db.Column(db.Date(), nullable=False)
    # informa se a pessoa é procurada pela polícia, para que possamos saber se ela é uma pessoa de interesse ou não
    wanted = db.Column(db.Boolean(), nullable=False, default=False)
    # razão pela qual a pessoa é procurada, para que possamos saber o motivo pelo qual ela é uma pessoa de interesse
    reason = db.Column(db.String(200), nullable=True, default=None)
    created_at = db.Column(db.DateTime(), nullable=False,
                           default=datetime.utcnow)
    # cascade facilita a exclusão de todas as embeddings associadas a uma pessoa quando ela é excluída do banco de dados
    embeddings = db.relationship(
        "EmbeddingModel",
        back_populates="person",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def __init__(self, name, date_birth, wanted=False, reason=None) -> None:
        self.name = name
        self.date_birth = date_birth
        self.wanted = wanted
        self.reason = reason

    @classmethod
    def find_by_id(cls, person_id) -> "PersonModel | None":
        return cls.query.filter_by(id=person_id).first()

    @classmethod
    def find_all(cls) -> list["PersonModel"]:
        return cls.query.all()

    def save_to_db(self) -> None:
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self) -> None:
        db.session.delete(self)
        db.session.commit()
