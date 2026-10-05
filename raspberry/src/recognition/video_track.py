import logging
import asyncio
import time
from collections.abc import Callable
from fractions import Fraction


logger = logging.getLogger(__name__)


def create_latest_frame_video_track(
    get_latest_frame: Callable[[], object | None],
    frames_per_second: int = 20,
):
    import av
    from aiortc import VideoStreamTrack
    from aiortc.mediastreams import MediaStreamError

    clock_rate = 90_000

    class LatestFrameVideoTrack(VideoStreamTrack):
        def __init__(self) -> None:
            super().__init__()
            self._frame_interval = 1 / frames_per_second
            self._next_frame_at = 0.0
            self._pts_increment = round(clock_rate * self._frame_interval)
            self._last_pts = -self._pts_increment

        async def recv(self):
            while True:
                if self.readyState != "live":
                    raise MediaStreamError
                frame = get_latest_frame()
                if frame is not None:
                    break
                await asyncio.sleep(0.02)

            now = time.monotonic()
            delay = self._next_frame_at - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_frame_at = max(self._next_frame_at, now) + self._frame_interval

            video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
            self._last_pts += self._pts_increment
            video_frame.pts = self._last_pts
            video_frame.time_base = Fraction(1, clock_rate)
            return video_frame

    return LatestFrameVideoTrack()
