from picamera2 import Picamera2
import time

picam2 = Picamera2()

config = picam2.create_still_configuration(
    main={"size": (2592, 1944)}
)

picam2.configure(config)
picam2.start()

time.sleep(2)

picam2.capture_file("testeCam.jpg")

picam2.stop()

print("Foto capturada!")