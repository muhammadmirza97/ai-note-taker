import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class Readiness:
    type: str = "none"
    port: int | None = None
    text: str = ""
    timeout_seconds: int = 60


def infer_port_from_url(url: str) -> int | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.port


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(port: int, timeout_seconds: int, stop_requested=None) -> bool:
    deadline = time.time() + max(1, int(timeout_seconds or 60))
    while time.time() < deadline:
        if stop_requested and stop_requested():
            return False
        if is_port_open(port):
            return True
        time.sleep(0.4)
    return False


def port_freed(port: int, timeout_seconds: int = 10) -> bool:
    deadline = time.time() + max(1, int(timeout_seconds))
    while time.time() < deadline:
        if not is_port_open(port):
            return True
        time.sleep(0.3)
    return not is_port_open(port)
