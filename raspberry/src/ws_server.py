import asyncio
import json
import logging
import threading
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed


from sync import get_sync_status


logger = logging.getLogger(__name__)


class DetectionWebSocketServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: set[Any] = set()
        self._camera_online = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._started = threading.Event()
        self._stopped = threading.Event()
        self._closed: asyncio.Event | None = None
        self._startup_error: BaseException | None = None
        self._thread: threading.Thread | None = None
        self._frame_lock = threading.Lock()
        self._latest_frame = None

    def start(self, timeout: float = 10) -> None:
        if self._thread and self._thread.is_alive():
            if self.is_running:
                return
            if not self._started.wait(timeout):
                raise TimeoutError("Timed out while starting the frontend WebSocket server.")
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise TimeoutError("Frontend WebSocket server thread did not stop.")

        self._started.clear()
        self._startup_error = None
        self._loop = None
        self._server = None
        self._closed = None
        self._thread = threading.Thread(
            target=self._run,
            name="frontend-websocket",
            daemon=True,
        )
        self._thread.start()
        if not self._started.wait(timeout):
            raise TimeoutError("Timed out while starting the frontend WebSocket server.")
        if self._startup_error:
            raise RuntimeError("Could not start the frontend WebSocket server.") from self._startup_error

    @property
    def is_running(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
            and self._loop
            and self._loop.is_running()
        )

    def set_camera_online(self, online: bool) -> None:
        self._camera_online = online
        if not online:
            with self._frame_lock:
                self._latest_frame = None
        try:
            self.broadcast(
                {
                    "type": "status",
                    "camera_online": online,
                    "sync": get_sync_status(),
                }
            )
        except Exception:
            logger.exception("Could not broadcast camera status.")

    def update_video_frame(self, frame) -> None:
        try:
            snapshot = frame.copy()
            with self._frame_lock:
                self._latest_frame = snapshot
        except Exception:
            logger.exception("Could not update the frame for WebRTC streaming.")

    def broadcast(self, message: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None or not loop.is_running():
            return

        coroutine = self._broadcast(message)
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
            future.add_done_callback(self._log_broadcast_error)
        except RuntimeError:
            coroutine.close()
            logger.exception("WebSocket event loop stopped before message delivery.")

    def stop(self, timeout: float = 5) -> None:
        loop = self._loop
        closed = self._closed
        if loop and loop.is_running() and closed:
            loop.call_soon_threadsafe(closed.set)
        if self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise TimeoutError("Frontend WebSocket server did not stop in time.")

    async def _serve(self) -> None:
        self._closed = asyncio.Event()
        self._server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=20,
            max_size=1024 * 1024,
        )
        self._started.set()
        logger.info("Frontend WebSocket listening on %s:%d.", self.host, self.port)
        await self._closed.wait()
        self._server.close()
        await self._server.wait_closed()

    async def _handle_client(self, websocket) -> None:
        self._clients.add(websocket)
        logger.info("Frontend connected to WebSocket (%d client(s)).", len(self._clients))
        peer = None
        pending_candidates = []
        try:
            await websocket.send(
                json.dumps(
                    {
                        "type": "status",
                        "camera_online": self._camera_online,
                        "sync": get_sync_status(),
                    }
                )
            )

            peer = await self._create_video_peer(websocket)
            async for raw_message in websocket:
                message = self._parse_message(raw_message)
                if message is None or peer is None:
                    continue

                message_type = message.get("type")
                if message_type == "answer":
                    from aiortc import RTCSessionDescription

                    await peer.setRemoteDescription(
                        RTCSessionDescription(
                            sdp=message["sdp"]["sdp"],
                            type=message["sdp"]["type"],
                        )
                    )
                    for candidate in pending_candidates:
                        await peer.addIceCandidate(candidate)
                    pending_candidates.clear()
                elif message_type == "ice-candidate":
                    from aiortc.sdp import candidate_from_sdp

                    candidate_data = message.get("candidate")
                    if not isinstance(candidate_data, dict):
                        logger.warning("Ignoring invalid WebRTC ICE candidate.")
                        continue
                    candidate_sdp = candidate_data.get("candidate")
                    if not isinstance(candidate_sdp, str):
                        continue
                    candidate = candidate_from_sdp(
                        candidate_sdp.removeprefix("candidate:")
                    )
                    candidate.sdpMid = candidate_data.get("sdpMid")
                    candidate.sdpMLineIndex = candidate_data.get("sdpMLineIndex")
                    if peer.remoteDescription is None:
                        pending_candidates.append(candidate)
                    else:
                        await peer.addIceCandidate(candidate)
        except ConnectionClosed:
            pass
        except Exception:
            logger.exception("WebSocket signaling failed for a frontend client.")
        finally:
            if peer is not None:
                try:
                    await peer.close()
                except Exception:
                    logger.exception("Could not close WebRTC peer cleanly.")
            self._clients.discard(websocket)
            logger.info("Frontend disconnected from WebSocket.")

    async def _create_video_peer(self, websocket):
        peer = None
        try:
            from aiortc import (
                RTCConfiguration,
                RTCIceServer,
                RTCPeerConnection,
            )
            from recognition.video_track import create_latest_frame_video_track

            peer = RTCPeerConnection(
                configuration=RTCConfiguration(
                    iceServers=[
                        RTCIceServer(urls="stun:stun.l.google.com:19302")
                    ]
                )
            )
            peer.addTrack(create_latest_frame_video_track(self._get_latest_frame))

            @peer.on("connectionstatechange")
            async def on_connection_state_change():
                if peer.connectionState in {"failed", "closed"}:
                    logger.warning(
                        "WebRTC peer entered %s state; reconnecting the frontend.",
                        peer.connectionState,
                    )
                    await websocket.close(
                        code=1011,
                        reason="WebRTC connection failed",
                    )

            offer = await peer.createOffer()
            await peer.setLocalDescription(offer)
            await websocket.send(
                json.dumps(
                    {
                        "type": "offer",
                        "sdp": {
                            "type": peer.localDescription.type,
                            "sdp": peer.localDescription.sdp,
                        },
                    }
                )
            )
            logger.info("Sent WebRTC video offer to frontend.")
            return peer
        except Exception:
            logger.exception(
                "Could not negotiate WebRTC; closing this connection so the frontend retries."
            )
            if peer is not None:
                try:
                    await peer.close()
                except Exception:
                    logger.exception("Could not close failed WebRTC peer.")
            await websocket.close(code=1011, reason="WebRTC negotiation failed")
            return None

    def _get_latest_frame(self):
        with self._frame_lock:
            return self._latest_frame

    @staticmethod
    def _parse_message(raw_message: str) -> dict[str, Any] | None:
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("Ignoring malformed frontend WebSocket message.")
            return None
        if not isinstance(message, dict):
            logger.warning("Ignoring non-object frontend WebSocket message.")
            return None

        if message.get("type") == "answer":
            sdp = message.get("sdp")
            if (
                not isinstance(sdp, dict)
                or not isinstance(sdp.get("sdp"), str)
                or sdp.get("type") != "answer"
            ):
                logger.warning("Ignoring malformed WebRTC answer.")
                return None
        elif message.get("type") == "ice-candidate":
            if not isinstance(message.get("candidate"), dict):
                logger.warning("Ignoring malformed WebRTC ICE candidate.")
                return None
        else:
            logger.debug(
                "Ignoring unsupported frontend WebSocket message type: %r.",
                message.get("type"),
            )
            return None
        return message

    async def _broadcast(self, message: dict[str, Any]) -> None:
        if not self._clients:
            return

        payload = json.dumps(message, separators=(",", ":"), allow_nan=False)
        clients = tuple(self._clients)
        results = await asyncio.gather(
            *(client.send(payload) for client in clients),
            return_exceptions=True,
        )
        for client, result in zip(clients, results):
            if isinstance(result, Exception):
                self._clients.discard(client)
                logger.warning("Could not deliver WebSocket message: %s", result)

    @staticmethod
    def _log_broadcast_error(future) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Could not broadcast a frontend WebSocket message.")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._serve())
        except Exception as error:
            self._startup_error = error
            self._started.set()
            logger.exception("Frontend WebSocket server stopped unexpectedly.")
        finally:
            loop.close()
            self._stopped.set()
