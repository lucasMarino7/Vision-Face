from sqlalchemy.orm import Mapped, mapped_column

from .. import Base


class SyncChange(Base):
    __tablename__ = "sync_change"

    version: Mapped[int] = mapped_column(primary_key=True)
