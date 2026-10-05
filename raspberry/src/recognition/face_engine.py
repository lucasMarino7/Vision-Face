import logging

import numpy as np


logger = logging.getLogger(__name__)


class FaceEngine:
    def __init__(
        self,
        model_name: str = "buffalo_l",
        detection_size: tuple[int, int] = (640, 640),
    ) -> None:
        from insightface.app import FaceAnalysis

        self.detection_size = detection_size
        logger.info("Loading InsightFace model %s.", model_name)
        self._app = FaceAnalysis(
            name=model_name,
            providers=["CPUExecutionProvider"],
        )
        self._app.prepare(ctx_id=-1, det_size=detection_size)
        logger.info("InsightFace model %s is ready.", model_name)

    def process(self, frame) -> list[dict[str, object]]:
        results = []
        for face in self._app.get(frame):
            embedding = np.asarray(face.embedding, dtype=np.float32)
            magnitude = float(np.linalg.norm(embedding))
            if not np.isfinite(magnitude) or magnitude == 0:
                logger.warning("Ignoring face detection with an invalid embedding.")
                continue

            results.append(
                {
                    "bbox": np.asarray(face.bbox, dtype=int).tolist(),
                    "embedding": embedding / magnitude,
                    "det_score": float(face.det_score),
                }
            )
        return results
