import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from database import PERSON_CACHE, PERSON_CACHE_LOCK
from database.chroma import face_collection, search_embedding
from .camera import Camera
from .face_engine import FaceEngine
from ws_server import DetectionWebSocketServer


logger = logging.getLogger(__name__)


def run_recognition_loop(
    stop_event: threading.Event,
    websocket_server: DetectionWebSocketServer,
) -> None:
    model_name = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")
    minimum_detection_score = _environment_float(
        "FACE_MIN_DETECTION_SCORE",
        default=0.5,
        minimum=0.0,
        maximum=1.0,
    )
    cooldown_seconds = _environment_float(
        "FACE_DETECTION_COOLDOWN_SECONDS",
        default=5.0,
        minimum=0.0,
    )
    configured_threshold = os.getenv("FACE_MATCH_DISTANCE_THRESHOLD") or None
    log_full_embedding = os.getenv("FACE_LOG_FULL_EMBEDDING", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    if configured_threshold:
        try:
            value = float(configured_threshold)
            if not math.isfinite(value) or value < 0:
                raise ValueError
        except ValueError:
            logger.error(
                "Invalid FACE_MATCH_DISTANCE_THRESHOLD=%r; using metric default.",
                configured_threshold,
            )
            configured_threshold = None

    engine = None
    last_sent_by_person: dict[int, float] = {}
    last_status_at = 0.0
    fps_frames = 0
    fps_started_at = time.monotonic()
    camera_fps = 0.0
    camera = None
    websocket_started = False
    next_websocket_retry = 0.0

    logger.info("Face recognition loop started.")
    while not stop_event.is_set():
        now = time.monotonic()
        if not websocket_started and now >= next_websocket_retry:
            try:
                websocket_server.start()
                websocket_started = True
            except Exception:
                logger.exception("WebSocket startup failed; retrying in 5 seconds.")
                next_websocket_retry = now + 5
        elif websocket_started and not websocket_server.is_running:
            websocket_started = False

        if engine is None:
            try:
                engine = FaceEngine(model_name=model_name)
            except Exception:
                logger.exception("Face model initialization failed; retrying in 10 seconds.")
                stop_event.wait(10)
                continue

        if camera is None:
            try:
                camera = Camera()
                camera.start()
                _set_camera_online(websocket_server, True)
            except Exception:
                logger.exception("Camera startup failed; retrying in 5 seconds.")
                _close_camera(camera)
                camera = None
                _set_camera_online(websocket_server, False)
                stop_event.wait(5)
                continue

        try:
            frame = camera.capture()
        except Exception:
            logger.exception("Camera capture failed; restarting the camera.")
            _set_camera_online(websocket_server, False)
            _close_camera(camera)
            camera = None
            stop_event.wait(2)
            continue

        try:
            frame_height, frame_width = frame.shape[:2]
            fps_frames += 1
            websocket_server.update_video_frame(frame)
            faces = engine.process(frame)
        except Exception:
            logger.exception("Face detection failed for the captured frame.")
            stop_event.wait(0.1)
            continue

        now = time.monotonic()
        if now - last_status_at >= 1:
            elapsed = now - fps_started_at
            if elapsed > 0:
                camera_fps = fps_frames / elapsed
            fps_frames = 0
            fps_started_at = now
            _broadcast(
                websocket_server,
                {
                    "type": "status",
                    "camera_online": True,
                    "fps": round(camera_fps, 1),
                }
            )
            last_status_at = now

        try:
            live_faces = []
            for face in faces:
                try:
                    info = _process_face(
                        face=face,
                        minimum_detection_score=minimum_detection_score,
                        configured_threshold=configured_threshold,
                        cooldown_seconds=cooldown_seconds,
                        now=now,
                        last_sent_by_person=last_sent_by_person,
                        frame_width=frame_width,
                        frame_height=frame_height,
                        websocket_server=websocket_server,
                        log_full_embedding=log_full_embedding,
                        model_name=model_name,
                    )
                    if info is not None:
                        live_faces.append(info)
                except Exception:
                    logger.exception("Failed to process a face detection; continuing.")
            # caixas do frame atual (lista vazia limpa as caixas no frontend)
            _broadcast(
                websocket_server,
                {
                    "type": "faces",
                    "faces": live_faces,
                    "frame_size": {"width": frame_width, "height": frame_height},
                },
            )
        except Exception:
            logger.exception("Face detection results could not be processed.")
            stop_event.wait(0.1)

    _set_camera_online(websocket_server, False)
    _close_camera(camera)
    if websocket_started:
        try:
            websocket_server.stop()
        except Exception:
            logger.exception("WebSocket shutdown failed.")
    logger.info("Face recognition loop stopped.")


def _process_face(
    face: dict[str, Any],
    minimum_detection_score: float,
    configured_threshold: str | None,
    cooldown_seconds: float,
    now: float,
    last_sent_by_person: dict[int, float],
    frame_width: int,
    frame_height: int,
    websocket_server: DetectionWebSocketServer,
    log_full_embedding: bool = False,
    model_name: str = "buffalo_l",
) -> dict[str, Any] | None:
    embedding = face.get("embedding")
    embedding_details = _format_embedding(embedding, log_full_embedding)
    detection_score = face.get("det_score")
    if (
        not isinstance(detection_score, (int, float))
        or isinstance(detection_score, bool)
        or not math.isfinite(detection_score)
        or detection_score < minimum_detection_score
    ):
        logger.info(
            "Face detected: recognized=false reason=low_detector_score "
            "detector_score=%r minimum_detector_score=%.4f embedding=%s",
            detection_score,
            minimum_detection_score,
            embedding_details,
        )
        return None

    bbox = face.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        logger.warning("Ignoring face detection with invalid bounding box: %r", bbox)
        return None
    x1, y1, x2, y2 = (int(coordinate) for coordinate in bbox)
    if x2 <= x1 or y2 <= y1:
        logger.warning("Ignoring face detection with empty bounding box: %r", bbox)
        return None

    try:
        nearest = _find_nearest_person(
            embedding,
            configured_threshold=configured_threshold,
        )
    except Exception:
        logger.exception(
            "Face detected: recognition unavailable detector_score=%.4f embedding=%s",
            detection_score,
            embedding_details,
        )
        return None

    person = None
    recognized = False
    if nearest is not None and nearest["accepted"]:
        with PERSON_CACHE_LOCK:
            cached_person = PERSON_CACHE.get(nearest["person_id"])
            person = dict(cached_person) if cached_person else None
        recognized = person is not None

    if nearest is None:
        score_details = "score=unavailable (Chroma has no matching records)"
    else:
        score_details = _format_match_score(nearest)

    if recognized:
        logger.info(
            "Face detected: recognized=true person=%r person_id=%d "
            "detector_score=%.4f %s embedding=%s",
            person["name"],
            nearest["person_id"],
            detection_score,
            score_details,
            embedding_details,
        )
    else:
        nearest_person = nearest["person_id"] if nearest else None
        logger.info(
            "Face detected: recognized=false nearest_person_id=%s "
            "detector_score=%.4f %s embedding=%s",
            nearest_person,
            detection_score,
            score_details,
            embedding_details,
        )
        if nearest is not None and nearest["accepted"] and person is None:
            logger.warning(
                "Chroma matched person %d, but the person is absent from the RAM cache.",
                nearest["person_id"],
            )

    face_info = {
        "box": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
        "recognized": recognized,
        "name": person["name"] if recognized else None,
        "wanted": bool(person["wanted"]) if recognized else False,
    }

    # chave -1 representa rostos não reconhecidos (cooldown compartilhado)
    person_id = nearest["person_id"] if recognized else -1
    distance = nearest["distance"] if nearest is not None else None

    if now - last_sent_by_person.get(person_id, float("-inf")) < cooldown_seconds:
        return face_info

    _broadcast(
        websocket_server,
        {
            "type": "detection",
            "recognized": recognized,
            "person": _serialize_person(person) if recognized else None,
            "embedding": [round(float(value), 6) for value in embedding],
            "model": model_name,
            "box": {
                "x": x1,
                "y": y1,
                "width": x2 - x1,
                "height": y2 - y1,
            },
            "frame_size": {
                "width": frame_width,
                "height": frame_height,
            },
            "distance": distance,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    last_sent_by_person[person_id] = now
    return face_info


def _close_camera(camera) -> None:
    if camera is None:
        return
    try:
        camera.close()
    except Exception:
        logger.exception("Could not release the camera cleanly.")


def _find_nearest_person(
    embedding,
    configured_threshold: str | None,
) -> dict[str, Any] | None:
    result = search_embedding(embedding, n_results=1)
    ids = result.get("ids", [[]])
    if not ids or not ids[0]:
        return None

    metadatas = result.get("metadatas", [[]])
    distances = result.get("distances", [[]])
    if not metadatas or not metadatas[0] or not distances or not distances[0]:
        logger.error("Chroma returned an incomplete nearest-neighbor result: %r", result)
        return None

    metadata = metadatas[0][0]
    distance = distances[0][0]
    if not isinstance(metadata, dict) or not isinstance(metadata.get("person_id"), int):
        logger.error("Chroma result has invalid person metadata: %r", metadata)
        return None
    if (
        not isinstance(distance, (int, float))
        or isinstance(distance, bool)
        or not math.isfinite(distance)
    ):
        logger.error("Chroma returned a non-numeric distance: %r", distance)
        return None

    metric = (face_collection.metadata or {}).get("hnsw:space", "l2")
    default_threshold = 0.4 if metric == "cosine" else 0.9
    threshold = float(configured_threshold) if configured_threshold else default_threshold
    return {
        "person_id": metadata["person_id"],
        "distance": float(distance),
        "metric": metric,
        "threshold": threshold,
        "accepted": distance <= threshold,
    }


def _format_embedding(embedding, include_full: bool) -> str:
    try:
        values = [float(value) for value in embedding]
    except (OverflowError, TypeError, ValueError):
        return f"<invalid: {type(embedding).__name__}>"

    if not values or any(not math.isfinite(value) for value in values):
        return f"<invalid numeric vector, dimensions={len(values)}>"

    if include_full:
        return "[" + ", ".join(f"{value:.5f}" for value in values) + "]"

    preview = ", ".join(f"{value:.5f}" for value in values[:8])
    if len(values) > 8:
        preview += ", ..."
        if len(values) > 12:
            preview += ", " + ", ".join(f"{value:.5f}" for value in values[-4:])
        else:
            preview += ", " + ", ".join(f"{value:.5f}" for value in values[8:])
    return f"{preview} (dimensions={len(values)})"


def _format_match_score(match: dict[str, Any]) -> str:
    metric = match["metric"]
    distance = match["distance"]
    threshold = match["threshold"]
    if metric == "cosine":
        similarity = max(-1.0, min(1.0, 1.0 - distance))
        return (
            f"score=cosine_similarity:{similarity:.2%} "
            f"(distance={distance:.5f}, threshold={threshold:.5f}, "
            f"accepted={match['accepted']}; similarity is not a calibrated accuracy)"
        )
    return (
        f"score={metric}_distance:{distance:.5f} "
        f"(lower is better, threshold={threshold:.5f}, "
        f"accepted={match['accepted']})"
    )


def _serialize_person(person: dict[str, Any]) -> dict[str, Any]:
    date_birth = person.get("date_birth")
    return {
        "id": person["id"],
        "name": person["name"],
        "date_birth": (
            date_birth.isoformat()
            if hasattr(date_birth, "isoformat")
            else date_birth
        ),
        "wanted": bool(person["wanted"]),
        "reason": person.get("reason"),
    }


def _environment_float(
    name: str,
    default: float,
    minimum: float,
    maximum: float | None = None,
) -> float:
    raw_value = os.getenv(name)
    try:
        value = default if raw_value is None else float(raw_value)
        if (
            not math.isfinite(value)
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            raise ValueError
    except ValueError:
        logger.error("Invalid %s=%r; using default %s.", name, raw_value, default)
        return default
    return value


def _set_camera_online(websocket_server, online: bool) -> None:
    try:
        websocket_server.set_camera_online(online)
    except Exception:
        logger.exception("Could not publish camera status over WebSocket.")


def _broadcast(websocket_server, message: dict[str, Any]) -> None:
    try:
        websocket_server.broadcast(message)
    except Exception:
        logger.exception("Could not queue a WebSocket message.")
