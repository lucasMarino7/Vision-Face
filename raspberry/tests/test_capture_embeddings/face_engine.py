import numpy as np
from insightface.app import FaceAnalysis


class FaceEngine:

    def __init__(self):
        print("Carregando InsightFace...")

        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"]
        )

        self.app.prepare(
            ctx_id=-1,
            det_size=(640, 640)
        )

        print("InsightFace carregado.")

    def process(self, frame):
        """
        Recebe um frame RGB/BGR e retorna
        informações sobre todos os rostos encontrados.
        """

        faces = self.app.get(frame)

        results = []

        for face in faces:

            embedding = face.embedding

            # Normaliza o embedding
            embedding = embedding / np.linalg.norm(embedding)

            results.append({
                "bbox": face.bbox.astype(int).tolist(),
                "embedding": embedding,
                "det_score": float(face.det_score)
            })

        return results