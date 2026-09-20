from picamera2 import Picamera2
import time


class Camera:

    def __init__(self):
        self.picam2 = Picamera2()

        config = self.picam2.create_preview_configuration(
            main={
                "size": (1920, 1080),
                "format": "RGB888"
            }
        )

        self.picam2.configure(config)

    def start(self):
        self.picam2.start()
        time.sleep(1)

    def capture(self):
        return self.picam2.capture_array()

    def stop(self):
        self.picam2.stop()