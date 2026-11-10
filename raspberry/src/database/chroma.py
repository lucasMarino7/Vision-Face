import logging
import math
from threading import Lock
from typing import Sequence

import chromadb

from .database import DATABASE_PATH

logger = logging.getLogger(__name__)

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

# Pacotes do InsightFace que usam o mesmo modelo de reconhecimento (mesma "família")
# geram embeddings compatíveis entre si. Só vetores da mesma família podem ser comparados.
MODEL_FAMILIES = {
    "buffalo_l": "w600k_r50",
    "buffalo_m": "w600k_r50",
    "buffalo_s": "w600k_mbf",
    "buffalo_sc": "w600k_mbf",
}
# embeddings que já existiam no Chroma antes do campo "family" foram todas geradas com o buffalo_l
LEGACY_MODEL = "buffalo_l"


def embedding_family(model_name: str | None) -> str:
    """Família de compatibilidade do modelo; modelo desconhecido só é compatível com ele mesmo."""
    name = (model_name or "").strip()
    if name in MODEL_FAMILIES:
        return MODEL_FAMILIES[name]
    logger.warning(
        "Unknown embedding model %r; its vectors only match this exact model name.",
        name,
    )
    return f"unknown:{name}"


def backfill_embedding_families() -> int:
    """Marca com model/family os registros antigos, sem alterar vetores nem remover nada."""
    legacy_family = embedding_family(LEGACY_MODEL)
    with chroma_lock:
        records = face_collection.get(include=["metadatas"])
        ids = []
        metadatas = []
        for record_id, metadata in zip(records["ids"], records["metadatas"]):
            metadata = dict(metadata or {})
            if metadata.get("family"):
                continue
            metadata["model"] = LEGACY_MODEL
            metadata["family"] = legacy_family
            ids.append(record_id)
            metadatas.append(metadata)
        if ids:
            face_collection.update(ids=ids, metadatas=metadatas)
    return len(ids)


def add_embedding(
    embedding_id: str,
    embedding: Sequence[float],
    person_id: int,
    angle: str | None = None,
    model: str | None = None,
):
    model_name = (model or LEGACY_MODEL).strip()
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
                    "model": model_name,
                    "family": embedding_family(model_name),
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


def search_embedding(
    embedding: Sequence[float],
    n_results: int = 1,
    model: str | None = None,
):
    normalized_embedding = _normalize_embedding(embedding)
    # compara apenas com vetores gerados por modelos compatíveis com o modelo atual
    family = embedding_family(model or LEGACY_MODEL)

    with chroma_lock:
        return face_collection.query(
            query_embeddings=[normalized_embedding],
            n_results=n_results,
            where={"family": family},
        )


def _normalize_embedding(embedding: Sequence[float]) -> list[float]:
    vector = [float(value) for value in embedding]
    if not vector or any(not math.isfinite(value) for value in vector):
        raise ValueError("Face embeddings must contain finite numeric values.")

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        raise ValueError("Face embeddings cannot be zero vectors.")
    return [float(value / magnitude) for value in vector]