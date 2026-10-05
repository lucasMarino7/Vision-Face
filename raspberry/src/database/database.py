from pathlib import Path
from threading import Lock

import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "vision_face.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
PERSON_CACHE: dict[int, dict[str, object]] = {}
PERSON_CACHE_LOCK = Lock()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass


def init_database():
    from . import models

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    refresh_person_cache()


def refresh_person_cache() -> None:
    from .models import Person

    with SessionLocal() as session:
        people = session.scalars(select(Person)).all()

    cache = {person.id: _person_cache_entry(person) for person in people}
    with PERSON_CACHE_LOCK:
        PERSON_CACHE.clear()
        PERSON_CACHE.update(cache)


def cache_person(person: dict[str, object]) -> None:
    person_id = person.get("id")
    if not isinstance(person_id, int):
        logger.error("Person cache entry must have an integer id.")
        return

    with PERSON_CACHE_LOCK:
        PERSON_CACHE[person_id] = dict(person)


def remove_cached_person(person_id: int) -> None:
    with PERSON_CACHE_LOCK:
        PERSON_CACHE.pop(person_id, None)


def _person_cache_entry(person) -> dict[str, object]:
    return {
        "id": person.id,
        "name": person.name,
        "date_birth": person.date_birth,
        "wanted": person.wanted,
        "reason": person.reason,
        "created_at": person.created_at,
    }