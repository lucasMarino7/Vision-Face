import cv2

from camera import Camera
from face_engine import FaceEngine


def main():
    camera = Camera()
    engine = FaceEngine()

    camera.start()   

    try:
        while True:
            frame = camera.capture()
            faces = engine.process(frame)

            for face in faces:
                x1, y1, x2, y2 = face["bbox"]
                print(
                    "Rosto encontrado:",
                    face["embedding"].shape,
                    "score:",
                    face["det_score"]
                )

            #     cv2.rectangle(
            #         frame,
            #         (x1, y1),
            #         (x2, y2),
            #         (0, 255, 0),
            #         2
            #     )

            # cv2.imshow("Vision Face", frame)
            # if cv2.waitKey(1) & 0xFF == ord("q"):
            #     break
    finally:
        camera.stop()
        # cv2.destroyAllWindows()


if __name__ == "__main__":
    main()