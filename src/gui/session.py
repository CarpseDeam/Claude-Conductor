"""Session IPC — local TCP socket for sending follow-up prompts to a running GUI viewer."""

import json
import logging
import socket
import threading
from typing import Callable

logger = logging.getLogger(__name__)

_HOST = "127.0.0.1"
_HEADER_SIZE = 8  # 8-digit zero-padded message length


def find_free_port() -> int:
    """Find an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((_HOST, 0))
        return s.getsockname()[1]


def send_prompt(port: int, prompt: str) -> bool:
    """Send a follow-up prompt to a running GUI viewer. Returns True on success."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((_HOST, port))
            payload = json.dumps({"type": "prompt", "content": prompt}).encode("utf-8")
            header = f"{len(payload):08d}".encode("utf-8")
            s.sendall(header + payload)
            response = s.recv(1024).decode("utf-8")
            return response == "ok"
    except (ConnectionRefusedError, TimeoutError, OSError) as e:
        logger.warning(f"SessionIPC: Failed to send prompt to port {port}: {e}")
        return False


class SessionListener:
    """TCP listener that accepts follow-up prompts from the MCP server."""

    def __init__(self, on_prompt: Callable[[str], None]) -> None:
        self._on_prompt = on_prompt
        self._socket: socket.socket | None = None
        self._running = False
        self._port = 0

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> int:
        """Start listening. Returns the bound port."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((_HOST, 0))
        self._port = self._socket.getsockname()[1]
        self._socket.listen(1)
        self._socket.settimeout(1.0)
        self._running = True

        thread = threading.Thread(target=self._accept_loop, daemon=True)
        thread.start()
        logger.info(f"SessionIPC: Listening on port {self._port}")
        return self._port

    def stop(self) -> None:
        """Stop the listener."""
        self._running = False
        if self._socket:
            self._socket.close()
            self._socket = None

    def _accept_loop(self) -> None:
        """Accept connections and dispatch prompts."""
        while self._running:
            try:
                conn, _ = self._socket.accept()
                self._handle_connection(conn)
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_connection(self, conn: socket.socket) -> None:
        """Read one message from connection, dispatch it, respond."""
        try:
            header = conn.recv(_HEADER_SIZE)
            if len(header) < _HEADER_SIZE:
                conn.sendall(b"error")
                return

            msg_len = int(header.decode("utf-8"))
            data = b""
            while len(data) < msg_len:
                chunk = conn.recv(min(4096, msg_len - len(data)))
                if not chunk:
                    break
                data += chunk

            msg = json.loads(data.decode("utf-8"))
            if msg.get("type") == "prompt":
                self._on_prompt(msg["content"])
                conn.sendall(b"ok")
            else:
                conn.sendall(b"error")
        except Exception as e:
            logger.warning(f"SessionIPC: Connection handler error: {e}")
            try:
                conn.sendall(b"error")
            except OSError:
                pass
        finally:
            conn.close()
