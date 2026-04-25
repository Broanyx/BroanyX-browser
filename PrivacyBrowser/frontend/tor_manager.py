"""
tor_manager.py
--------------
Manages the lifecycle of a local Tor daemon using stem.
"""

import os
import shutil
import threading
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

TOR_SOCKS_HOST = "127.0.0.1"
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051

_C_PATHS = [
    # Desktop install (found on this machine)
    r"C:\Users\{user}\Desktop\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
    r"C:\Program Files\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
    r"C:\Program Files (x86)\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
    r"C:\Users\{user}\AppData\Local\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
    r"C:\Users\{user}\Downloads\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
    r"C:\tor\tor.exe",
    r"C:\tor\Tor\tor.exe",
]

_D_PATHS = [
    r"D:\ml\tor-expert-bundle-windows-x86_64-15.0.9\tor\tor.exe",
    r"D:\tor\tor.exe",
    r"D:\tor\Tor\tor.exe",
    r"D:\Tor\tor.exe",
    r"D:\Tor\Tor\tor.exe",
    r"D:\TorBrowser\Browser\TorBrowser\Tor\tor.exe",
    r"D:\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
    r"D:\tor-win64\Tor\tor.exe",
    r"D:\tor-expert-bundle\Tor\tor.exe",
    r"D:\tor-expert-bundle\tor\tor.exe",
]

TOR_SEARCH_PATHS = _C_PATHS + _D_PATHS


def _scan_drive_for_tor(drive: str) -> Optional[str]:
    skip_dirs = {"Windows", "System32", "$Recycle.Bin", "ProgramData",
                 "AppData", "node_modules", ".git", "venv", "__pycache__"}
    try:
        for root, dirs, files in os.walk(drive):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            if "tor.exe" in files:
                found = os.path.join(root, "tor.exe")
                if "privacybrowser" not in found.lower() and "broswer" not in found.lower():
                    logger.info(f"Found tor.exe via drive scan: {found}")
                    return found
    except PermissionError:
        pass
    return None


def find_tor_executable() -> Optional[str]:
    tor_in_path = shutil.which("tor")
    if tor_in_path:
        logger.info(f"Found tor in PATH: {tor_in_path}")
        return tor_in_path

    username = os.environ.get("USERNAME", "")
    for path_template in TOR_SEARCH_PATHS:
        path = path_template.replace("{user}", username)
        if os.path.isfile(path):
            logger.info(f"Found tor at: {path}")
            return path

    # Also scan Desktop explicitly (common non-standard install location)
    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    if os.path.isdir(desktop):
        desktop_found = _scan_drive_for_tor(desktop)
        if desktop_found:
            return desktop_found

    logger.info("tor.exe not found in known paths — scanning D:\\ …")
    found = _scan_drive_for_tor("D:\\")
    if found:
        return found

    logger.warning("tor.exe not found anywhere.")
    return None


class TorManager:
    """Manages a Tor subprocess and tracks connection status."""

    def __init__(self, status_callback: Optional[Callable[[bool, str], None]] = None):
        self._process = None
        self._tor_path: Optional[str] = None
        self._connected = False
        self._status_callback = status_callback
        self._thread: Optional[threading.Thread] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def socks_host(self) -> str:
        return TOR_SOCKS_HOST

    @property
    def socks_port(self) -> int:
        return TOR_SOCKS_PORT

    def start(self):
        self._thread = threading.Thread(target=self._launch_tor, daemon=True)
        self._thread.start()

    def stop(self):
        if self._process is not None:
            try:
                self._process.kill()
                logger.info("Tor process terminated.")
            except Exception as e:
                logger.warning(f"Error stopping Tor: {e}")
        self._connected = False

    def _emit_status(self, connected: bool, message: str):
        self._connected = connected
        if self._status_callback:
            self._status_callback(connected, message)

    def _launch_tor(self):
        try:
            from stem.process import launch_tor_with_config
        except ImportError:
            self._emit_status(False, "stem library not installed. Run: pip install stem")
            return

        tor_path = find_tor_executable()
        if tor_path is None:
            self._emit_status(
                False,
                "Tor executable not found.\n"
                "Install from https://www.torproject.org/download/ and add to PATH.",
            )
            return

        self._tor_path = tor_path
        self._emit_status(False, "Starting Tor… (10-60 seconds)")

        try:
            data_dir = os.path.join(os.path.dirname(__file__), ".tor_data")
            os.makedirs(data_dir, exist_ok=True)

            self._process = launch_tor_with_config(
                tor_cmd=tor_path,
                config={
                    "SocksPort": str(TOR_SOCKS_PORT),
                    "ControlPort": str(TOR_CONTROL_PORT),
                    "DataDirectory": data_dir,
                    "Log": "notice stdout",
                    "StrictNodes": "0",
                    "UseEntryGuards": "1",
                    "AvoidDiskWrites": "0",
                    "UseMicrodescriptors": "1",
                },
                init_msg_handler=self._handle_bootstrap_message,
                take_ownership=True,
            )
            self._emit_status(True, "Tor connected — all traffic is encrypted and anonymised.")

        except OSError as e:
            self._emit_status(False, f"Tor process error: {e}")
        except Exception as e:
            self._emit_status(False, f"Tor failed to start: {e}")

    def _handle_bootstrap_message(self, line: str):
        logger.info(f"[Tor] {line}")
        if "Bootstrapped" in line:
            try:
                percent = int(line.split("Bootstrapped")[1].split("%")[0].strip())
                self._emit_status(False, f"Tor bootstrapping… {percent}%")
            except (IndexError, ValueError):
                self._emit_status(False, f"Tor: {line.strip()}")
