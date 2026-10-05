from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .. import Base

class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    # person ou embedding, para saber qual tabela foi alterada
    table_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # id da pessoa ou id da embedding, para saber qual registro foi alterado
    data_id: Mapped[int] = mapped_column(
        nullable=False
    )
    # operação que foi realizada na tabela person, CREATE, UPDATE ou DELETE, para saber qual operação foi realizada na tabela person
    operation: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    # status da caixa de menssagem, PENDING or DONE, para saber se a mensagem já foi processada ou não
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING"
    )