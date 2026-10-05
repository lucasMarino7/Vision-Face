import time


class Camera:
    def __init__(self, size: tuple[int, int] = (1280, 720)) -> None:
        from picamera2 import Picamera2

        self._camera = Picamera2()
        self._started = False
        try:
            configuration = self._camera.create_video_configuration(
                main={"size": size, "format": "RGB888"},
                buffer_count=4,
            )
            self._camera.configure(configuration)
        except Exception:
            self._camera.close()
            raise

    def start(self) -> None:
        if self._started:
            return
        self._camera.start()
        self._started = True
        time.sleep(1)

    def capture(self):
        if not self._started:
            raise RuntimeError("Camera must be started before capturing frames.")
        return self._camera.capture_array()

    def stop(self) -> None:
        if self._started:
            self._camera.stop()
            self._started = False

    def close(self) -> None:
        try:
            self.stop()
        finally:
            self._camera.close()
