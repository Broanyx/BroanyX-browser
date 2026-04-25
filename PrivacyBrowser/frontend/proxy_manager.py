"""
proxy_manager.py
----------------
Manages the lifecycle of the Go proxy_engine subprocess.

Starts proxy_engine.exe when the browser opens.
Terminates it when the browser closes.
Polls the /__proxy_status endpoint to confirm it's alive.
"""

import os
import subprocess
import threading
import logging
import time
from typing import Optional, Callable

logger = logging.getLogger(__name__)

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
STATUS_URL = f"http://{PROXY_HOST}:{PROXY_PORT}/__proxy_status"

# Resolve path to the compiled Go binary (sibling ../backend/ directory)
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_HERE, "..", "backend")
PROXY_EXECUTABLE = os.path.join(_BACKEND_DIR, "proxy_engine.exe")


class ProxyManager:
    """
    Manages the Go proxy_engine subprocess.

    Usage:
        pm = ProxyManager(status_callback=fn)
        pm.start()
        ...
        pm.stop()
    """

    def __init__(self, status_callback: Optional[Callable[[bool, str], None]] = None):
        self._process: Optional[subprocess.Popen] = None
        self._status_callback = status_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def proxy_host(self) -> str:
        return PROXY_HOST

    @property
    def proxy_port(self) -> int:
        return PROXY_PORT

    def start(self):
        """Launch Go proxy in a background thread (non-blocking)."""
        self._thread = threading.Thread(target=self._launch_proxy, daemon=True)
        self._thread.start()

    def stop(self):
        """Terminate the Go proxy process."""
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
                logger.info("Go proxy terminated.")
            except Exception as e:
                logger.warning(f"Error stopping Go proxy: {e}")
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._running = False

    def _emit_status(self, running: bool, message: str):
        self._running = running
        if self._status_callback:
            self._status_callback(running, message)

    def _launch_proxy(self):
        exe = PROXY_EXECUTABLE
        if not os.path.isfile(exe):
            msg = (
                f"Go proxy executable not found at:\n{exe}\n\n"
                "Please compile it first:\n"
                "  cd backend && go build -o proxy_engine.exe ."
            )
            logger.error(msg)
            self._emit_status(False, msg)
            return

        logger.info(f"Starting Go proxy: {exe}")
        self._emit_status(False, "Starting Go proxy engine…")

        try:
            self._process = subprocess.Popen(
                [exe],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=_BACKEND_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as e:
            self._emit_status(False, f"Failed to launch Go proxy: {e}")
            return

        # Stream proxy logs to Python logger
        threading.Thread(
            target=self._stream_proxy_logs,
            args=(self._process,),
            daemon=True,
        ).start()

        # Poll until the proxy is accepting connections
        self._wait_for_proxy_ready()

    def _wait_for_proxy_ready(self, max_wait: float = 30.0):
        """Poll STATUS_URL until proxy responds or timeout."""
        import urllib.request
        import urllib.error

        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            if self._process and self._process.poll() is not None:
                self._emit_status(False, "Go proxy exited unexpectedly before becoming ready.")
                return
            try:
                with urllib.request.urlopen(STATUS_URL, timeout=2) as resp:
                    if resp.status == 200:
                        self._emit_status(True, f"Go proxy active on {PROXY_HOST}:{PROXY_PORT}")
                        logger.info("✅ Go proxy is ready.")
                        return
            except Exception:
                pass
            time.sleep(0.5)

        self._emit_status(False, f"Go proxy did not become ready within {max_wait}s.")

    def _stream_proxy_logs(self, proc: subprocess.Popen):
        """Read and forward Go proxy stdout to Python logger."""
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    logger.info(f"[go-proxy] {line}")
        except Exception:
            pass
