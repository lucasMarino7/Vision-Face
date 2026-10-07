import math
from threading import Lock
from typing import Sequence

import chromadb

from .database import DATABASE_PATH

CHROMA_PATH = DATABASE_PATH.parent / "chroma"
COLLECTION_NAME = "face_embeddings"

CHROMA_PATH.mkdir(parents=True, exist_ok=True)

client = chromadb.PersistentClient(
    path=str(CHROMA_PATH)
)

face_collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)

chroma_lock = Lock()


def add_embedding(
    embedding_id: str,
    embedding: Sequence[float],
    person_id: int,
    angle: str | None = None,
):
    normalized_embedding = _normalize_embedding(embedding)

    with chroma_lock:
        face_collection.upsert(
            ids=[embedding_id],
            embeddings=[normalized_embedding],
            metadatas=[
                {
                    "person_id": person_id,
                    "embedding_id": int(embedding_id),
                    # Chroma não aceita None em metadados
                    "angle": angle or "",
                }
            ],
        )


def delete_embedding(embedding_id: str):
    with chroma_lock:
        face_collection.delete(
            ids=[embedding_id]
    )


def delete_person_embeddings(person_id: int):
    with chroma_lock:
        face_collection.delete(
            where={
                "person_id": person_id
            }
        )


def search_embedding(embedding: Sequence[float], n_results: int = 1):
    normalized_embedding = _normalize_embedding(embedding)

    with chroma_lock:
        return face_collection.query(
            query_embeddings=[normalized_embedding],
            n_results=n_results
        )


def _normalize_embedding(embedding: Sequence[float]) -> list[float]:
    vector = [float(value) for value in embedding]
    if not vector or any(not math.isfinite(value) for value in vector):
        raise ValueError("Face embeddings must contain finite numeric values.")

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        raise ValueError("Face embeddings cannot be zero vectors.")
    return [float(value / magnitude) for value in vector]