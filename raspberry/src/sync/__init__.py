import logging
import os
import time
from datetime import date, datetime, timezone
from threading import Event, Lock
from typing import Any

from chromadb.errors import ChromaError
import requests
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from database import cache_person, remove_cached_person
from database.chroma import add_embedding, delete_embedding, delete_person_embeddings
from database.database import SessionLocal
from database.models import Outbox, Person, SyncChange


logger = logging.getLogger(__name__)

_status_lock = Lock()
_status: dict[str, Any] = {
    "syncing": False,
    "backend_online": None,
    "last_sync_at": None,
    "next_sync_at": None,
    "interval_seconds": None,
}


def _update_status(**values: Any) -> None:
    with _status_lock:
        _status.update(values)


def get_sync_status() -> dict[str, Any]:
    """Estado da sincronização para o frontend (datas em UTC ISO-8601)."""
    with _status_lock:
        status = dict(_status)
    next_sync_at = status["next_sync_at"]
    status["next_sync_in"] = (
        None
        if next_sync_at is None
        else max(0.0, round(next_sync_at - time.time(), 1))
    )
    for key in ("last_sync_at", "next_sync_at"):
        if status[key] is not None:
            status[key] = datetime.fromtimestamp(status[key], timezone.utc).isoformat()
    return status


class Synchronizer:
    def __init__(
        self,
        api_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        configured_url = api_url or os.getenv("API_URL")
        if not configured_url:
            raise ValueError("API_URL must be configured for backend synchronization.")

        self.api_url = configured_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")

    def synchronize_once(self) -> int:
        self.process_pending_outbox()

        status = self._get_json(f"{self.api_url}/sync/status")
        if not isinstance(status, dict):
            logger.error("Invalid sync status response: %r", status)
            return 0
        server_version = self._required_int(status, "latest_snapshot_version")
        local_version = self._get_local_version()
        if server_version < local_version:
            logger.warning(
                f"Local sync version {local_version} is newer than backend version "
                f"{server_version}; a full resynchronization is required."
            )
            return 0
        if server_version == local_version:
            return 0

        delta = self._get_json(f"{self.api_url}/sync/delta/{local_version}")
        if not isinstance(delta, dict):
            logger.error("Invalid delta response: %r", delta)
            return 0
        changes = delta.get("items")
        if not isinstance(changes, list):
            logger.error("Delta response does not contain an 'items' list: %r", delta)
            return 0
        if not changes:
            logger.warning(
                "Backend reports version %d, but returned no changes after local version %d.",
                server_version,
                local_version,
            )
            return 0

        normalized_changes = [self._normalize_change(change) for change in changes]
        normalized_changes.sort(key=lambda change: change["version"])
        if any(
            later["version"] <= earlier["version"]
            for earlier, later in zip(normalized_changes, normalized_changes[1:])
        ):
            logger.error("Delta response contains duplicate or out-of-order versions: %r", changes)
            return 0

        embeddings = self._get_embedding_records(normalized_changes)
        applied = 0
        current_version = local_version
        for change in normalized_changes:
            version = change["version"]
            if version <= current_version:
                continue

            self._apply_change(change, embeddings)
            current_version = version
            applied += 1

        if not applied and current_version < server_version:
            logger.warning(
                "No changes were applied, but backend is at version %d (local version %d).",
                server_version,
                current_version,
            )

        self.process_pending_outbox()
        logger.info("Applied %d backend change(s), now at version %d.", applied, current_version)
        return applied

    def process_pending_outbox(self) -> int:
        with SessionLocal() as session:
            pending = session.scalars(
                select(Outbox)
                .where(Outbox.status == "PENDING")
                .order_by(Outbox.id)
            ).all()
            pending_items = [
                (item.id, item.table_name, item.data_id, item.operation)
                for item in pending
            ]

        processed = 0
        for outbox_id, table_name, data_id, operation in pending_items:
            if table_name != "person" or operation.lower() != "delete":
                logger.warning(
                    f"Unsupported outbox operation: {table_name}.{operation} "
                    f"(id={outbox_id})."
                )
                continue

            delete_person_embeddings(data_id)
            with SessionLocal.begin() as session:
                item = session.get(Outbox, outbox_id)
                if item is not None and item.status == "PENDING":
                    item.status = "DONE"
            processed += 1

        return processed

    def _apply_change(
        self,
        change: dict[str, Any],
        embeddings: dict[int, dict[str, Any]],
    ) -> None:
        table_name = change["table_name"]
        operation = change["operation"]
        register_id = change["register_id"]
        version = change["version"]

        if table_name == "person":
            if operation == "delete":
                with SessionLocal.begin() as session:
                    person = session.get(Person, register_id)
                    if person is not None:
                        session.delete(person)
                    session.add(
                        Outbox(
                            table_name="person",
                            data_id=register_id,
                            operation="delete",
                            status="PENDING",
                        )
                    )
                    session.add(SyncChange(version=version))
                remove_cached_person(register_id)
                return

            if operation not in {"insert", "update"}:
                logger.error(
                    "Unsupported person operation: %r (register_id=%d, version=%d).",
                    operation,
                    register_id,
                    version,
                )
                return

            person_data = self._get_person(register_id)
            if person_data is None:
                logger.warning(
                    "Person %d no longer exists while applying version %d.",
                    register_id,
                    version,
                )
                with SessionLocal.begin() as session:
                    session.add(SyncChange(version=version))
                return

            cache_entry = self._normalize_person(person_data, register_id)
            with SessionLocal.begin() as session:
                person = session.get(Person, register_id)
                if person is None:
                    person = Person(id=register_id, **{
                        key: value for key, value in cache_entry.items() if key != "id"
                    })
                    session.add(person)
                else:
                    for key, value in cache_entry.items():
                        if key != "id":
                            setattr(person, key, value)
                session.add(SyncChange(version=version))
            cache_person(cache_entry)
            return

        if table_name == "embedding":
            if operation == "delete":
                delete_embedding(str(register_id))
            elif operation in {"insert", "update"}:
                embedding = embeddings.get(register_id)
                if embedding is None:
                    logger.warning(
                        "Embedding %d no longer exists while applying version %d.",
                        register_id,
                        version,
                    )
                else:
                    self._store_embedding(embedding, register_id)
            else:
                logger.error(f"Unsupported embedding operation: {operation!r}.")
                return

            with SessionLocal.begin() as session:
                session.add(SyncChange(version=version))
            return

        logger.error(
            "Unsupported backend table in delta: %r (register_id=%d, operation=%r, version=%d).",
            table_name,
            register_id,
            operation,
            version,
        )

    def _get_embedding_records(
        self,
        changes: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        needs_embeddings = any(
            change["table_name"] == "embedding"
            and change["operation"] in {"insert", "update", "delete"}
            for change in changes
        )
        if not needs_embeddings:
            return {}

        response = self._get_json(f"{self.api_url}/embedding/")
        records = response if isinstance(response, list) else None
        if records is None:
            logger.error("The embedding endpoint must return a JSON list.")
            return {}

        indexed: dict[int, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                logger.error("The embedding endpoint returned an invalid record.")
                continue
            embedding_id = self._required_int(record, "id")
            indexed[embedding_id] = record
        return indexed

    def _get_person(self, person_id: int) -> dict[str, Any] | None:
        response = self.session.get(
            f"{self.api_url}/person/{person_id}",
            timeout=10,
        )
        if response.status_code == requests.codes.not_found:
            return None
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            logger.error("Person endpoint must return a JSON object for person_id=%d: %r", person_id, data)
            return None
        return data

    def _get_json(self, url: str) -> Any:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, (dict, list)):
            logger.error("Backend response from %s must be a JSON object or list: %r", url, data)
            return None
        return data

    def _get_local_version(self) -> int:
        with SessionLocal() as session:
            return session.scalar(select(func.max(SyncChange.version))) or 0

    @staticmethod
    def _normalize_change(change: Any) -> dict[str, Any]:
        if not isinstance(change, dict):
            raise ValueError("The delta response contains an invalid change.")
        version = Synchronizer._required_int(change, "version")
        register_id = Synchronizer._required_int(change, "register_id")
        table_name = change.get("table_name")
        operation = change.get("operation")
        if not isinstance(table_name, str) or not isinstance(operation, str):
            raise ValueError("Delta changes require string table_name and operation fields.")
        return {
            "version": version,
            "register_id": register_id,
            "table_name": table_name.lower(),
            "operation": operation.lower(),
        }

    @staticmethod
    def _required_int(data: dict[str, Any], field: str) -> int:
        value = data.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            logger.error(f"Backend field {field!r} must be a non-negative integer.")
            return 0
        return value

    @staticmethod
    def _normalize_person(data: dict[str, Any], person_id: int) -> dict[str, Any]:
        if Synchronizer._required_int(data, "id") != person_id:
            logger.error("Person endpoint returned an unexpected id for %d: %r", person_id, data)
            return {}

        name = data.get("name")
        wanted = data.get("wanted")
        reason = data.get("reason")
        date_birth_value = data.get("date_birth")
        created_at_value = data.get("created_at")
        if not isinstance(name, str):
            logger.error("Person response field 'name' must be a string.")
            return {}
        if not isinstance(wanted, bool):
            logger.error("Person response field 'wanted' must be a boolean.")
            return {}
        if reason is not None and not isinstance(reason, str):
            logger.error("Person response field 'reason' must be a string or null.")
            return {}
        if not isinstance(date_birth_value, str) or not isinstance(created_at_value, str):
            logger.error("Person response must contain date_birth and created_at strings.")
            return {}

        return {
            "id": person_id,
            "name": name,
            "date_birth": date.fromisoformat(date_birth_value),
            "wanted": wanted,
            "reason": reason,
            "created_at": datetime.fromisoformat(
                created_at_value.replace("Z", "+00:00")
            ),
        }

    @staticmethod
    def _store_embedding(data: dict[str, Any], embedding_id: int) -> None:
        if Synchronizer._required_int(data, "id") != embedding_id:
            logger.error("Embedding endpoint returned an unexpected id for %d: %r", embedding_id, data)
            return

        person_id = Synchronizer._required_int(data, "person_id")
        vector = data.get("embedding")
        if (
            not isinstance(vector, list)
            or len(vector) != 512
            or any(
                not isinstance(value, (int, float)) or isinstance(value, bool)
                for value in vector
            )
        ):
            logger.error("Embedding %d must contain exactly 512 numeric values.", embedding_id)
            return

        add_embedding(str(embedding_id), vector, person_id)


def run_sync_loop(stop_event: Event, interval_seconds: float = 30) -> None:
    synchronizer = Synchronizer()
    if interval_seconds <= 0:
        raise ValueError("Synchronization interval must be greater than zero.")

    logger.info("Starting backend synchronization every %.1f seconds.", interval_seconds)
    backend_online: bool | None = None
    attempt = 0
    _update_status(interval_seconds=interval_seconds, next_sync_at=time.time())
    while not stop_event.is_set():
        attempt += 1
        _update_status(syncing=True, next_sync_at=None)
        logger.info("Synchronization attempt #%d started (%s).", attempt, synchronizer.api_url)
        try:
            applied = synchronizer.synchronize_once()
            if backend_online is False:
                logger.info("Backend reachable again; synchronization resumed.")
            if applied:
                logger.info("Synchronization attempt #%d finished: %d change(s) applied.", attempt, applied)
            else:
                logger.info("Synchronization attempt #%d finished: already up to date.", attempt)
            backend_online = True
            _update_status(last_sync_at=time.time())
        except Exception as e:
            logger.error(
                "Synchronization attempt #%d failed: %s: %s. Retrying in %.0fs.",
                attempt,
                type(e).__name__,
                e,
                interval_seconds,
            )
            backend_online = False

        _update_status(
            syncing=False,
            backend_online=backend_online,
            next_sync_at=time.time() + interval_seconds,
        )
        if stop_event.wait(interval_seconds):
            break
