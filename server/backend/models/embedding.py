from backend.server.extensions import db
from datetime import datetime
from pgvector.sqlalchemy import Vector


class EmbeddingModel(db.Model):
    """
    tabela que conterá as embeddings faciais das pessoas cadastradas
    """
    __tablename__ = 'embedding'

    id = db.Column(db.Integer(), primary_key=True)
    # cascade delete, para que quando uma pessoa for deletada, todas as suas embeddings também sejam deletadas
    person_id = db.Column(
        db.Integer(),
        db.ForeignKey('person.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # embedding facial da pessoa, que é um vetor de 512 dimensões, gerado pelo modelo de IA
    embedding = db.Column(Vector(512), nullable=False)
    # nome do modelo de IA utilizado para gerar a embedding, para que possamos saber qual modelo foi utilizado
    model = db.Column(db.String(20), nullable=False)
    # tamanho da embedding como 512, 256, 128, etc, para que possamos saber qual tamanho foi utilizado para gerar a embedding
    dimension = db.Column(db.Integer(), nullable=False)
    # angulo do rosto da pessoa na imagem, para que possamos saber qual angulo foi utilizado para gerar a embedding
    angle = db.Column(
        db.String(20), nullable=False)
    created_at = db.Column(db.DateTime(), nullable=False,
                           default=datetime.utcnow)
    person = db.relationship("PersonModel", back_populates="embeddings")

    def __init__(self, person_id, embedding, model, angle, dimension) -> None:
        self.person_id = person_id
        self.embedding = embedding
        self.model = model
        self.angle = angle
        self.dimension = dimension

    @classmethod
    def find_by_id(cls, _id) -> "EmbeddingModel":
        return cls.query.filter_by(id=_id).first()

    @classmethod
    def find_all(cls) -> list["EmbeddingModel"]:
        return cls.query.all()

    def save_to_db(self) -> None:
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self) -> None:
        db.session.delete(self)
        db.session.commit()
