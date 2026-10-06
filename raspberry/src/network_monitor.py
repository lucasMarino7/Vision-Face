import logging
import subprocess
from pathlib import Path
from threading import Event

logger = logging.getLogger(__name__)

_NET_DIR = Path("/sys/class/net")


def _wifi_state() -> tuple[str, str | None]:
    """Retorna (estado, interface) do primeiro adaptador wifi; estado: up, down ou absent."""
    for interface in sorted(_NET_DIR.glob("wl*")):
        try:
            state = (interface / "operstate").read_text().strip()
        except OSError:
            continue
        return ("up" if state == "up" else "down"), interface.name
    return "absent", None


def _ssid(interface: str) -> str | None:
    try:
        result = subprocess.run(
            ["iwgetid", interface, "-r"], capture_output=True, text=True, timeout=3
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _ip_address(interface: str) -> str | None:
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", interface],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in result.stdout.splitlines():
        parts = line.split()
        if "inet" in parts:
            return parts[parts.index("inet") + 1].split("/")[0]
    return None


def _log_websocket_address(interface: str, port: int) -> None:
    ip = _ip_address(interface)
    if ip:
        logger.info("WebSocket address: ws://%s:%d", ip, port)
    else:
        logger.warning("Wi-Fi is up (%s) but has no IPv4 address yet.", interface)


def run_network_monitor(
    stop_event: Event, port: int = 8765, interval_seconds: float = 5
) -> None:
    """Loga mudanças de estado do wifi e o endereço do WebSocket ao conectar."""
    previous: str | None = None
    announced_ip: str | None = None
    while not stop_event.is_set():
        state, interface = _wifi_state()
        if state == "up":
            # o DHCP pode atrasar o IP; reanuncia quando o endereço aparecer ou mudar
            ip = _ip_address(interface)
            if ip and ip != announced_ip:
                if state == previous:
                    logger.info("WebSocket address: ws://%s:%d", ip, port)
                announced_ip = ip
        else:
            announced_ip = None
        if state != previous:
            if state == "up":
                ssid = _ssid(interface)
                if previous is None:
                    logger.info("Wi-Fi connected (%s%s).", interface, f", SSID {ssid}" if ssid else "")
                else:
                    logger.info("Wi-Fi reconnected (%s%s).", interface, f", SSID {ssid}" if ssid else "")
                _log_websocket_address(interface, port)
                announced_ip = _ip_address(interface)
            elif state == "down":
                if previous is None:
                    logger.warning("Wi-Fi is not connected (%s); waiting for connection.", interface)
                else:
                    logger.warning("Wi-Fi connection lost (%s); waiting to reconnect.", interface)
            elif previous is None:
                logger.info("No Wi-Fi interface found; network monitor idle.")
            previous = state
        if stop_event.wait(interval_seconds):
            break
