"""
tor_manager.py
--------------
Manages the lifecycle of a local Tor daemon process.

Uses the `stem` library to:
- Launch tor.exe with a minimal config
- Wait for bootstrap to reach 100%
- Provide SOCKS5 proxy connection details
- Cleanly terminate on exit
"""

import os
import shutil
import threading
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Default Tor SOCKS5 proxy settings
TOR_SOCKS_HOST = "127.0.0.1"
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051

# Common Windows Tor installation paths (C drive)
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

# D drive paths — covers common extraction folder names
_D_PATHS = [
    # User's extracted Expert Bundle (found via scan)
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
    """
    Last-resort: walk a drive looking for tor.exe.
    Skips system/hidden dirs. Stops at the first match found.
    """
    skip_dirs = {"Windows", "System32", "$Recycle.Bin", "ProgramData",
                 "AppData", "node_modules", ".git", "venv", "__pycache__"}
    try:
        for root, dirs, files in os.walk(drive):
            # Prune directories we know won't contain Tor
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            if "tor.exe" in files:
                found = os.path.join(root, "tor.exe")
                # Exclude our own venv or browser folder
                if "broswer" not in found.lower():
                    logger.info(f"Found tor.exe via drive scan: {found}")
                    return found
    except PermissionError:
        pass
    return None


def find_tor_executable() -> Optional[str]:
    """
    Locate the Tor executable using a multi-stage strategy:
      1. System PATH
      2. Known common installation paths (C + D drives)
      3. Recursive scan of D:\\ as a last resort
    Returns the full path string, or None if not found anywhere.
    """
    # 1. Check PATH
    tor_in_path = shutil.which("tor")
    if tor_in_path:
        logger.info(f"Found tor in PATH: {tor_in_path}")
        return tor_in_path

    # 2. Check known fixed paths
    username = os.environ.get("USERNAME", "")
    for path_template in TOR_SEARCH_PATHS:
        path = path_template.replace("{user}", username)
        if os.path.isfile(path):
            logger.info(f"Found tor at: {path}")
            return path

    # 3. Scan Desktop explicitly (common non-standard install location on this machine)
    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    if os.path.isdir(desktop):
        desktop_found = _scan_drive_for_tor(desktop)
        if desktop_found:
            return desktop_found

    # 4. Scan D:\ recursively (catches any extraction layout)
    logger.info("tor.exe not found in known paths — scanning D:\\ (may take a moment)...")
    found = _scan_drive_for_tor("D:\\")
    if found:
        return found

    logger.warning("tor.exe not found anywhere. Checked PATH + common locations + D:\\ scan.")
    return None


class TorManager:
    """
    Manages a Tor subprocess and tracks its connection status.
    
    Usage:
        manager = TorManager(status_callback=my_fn)
        manager.start()          # Non-blocking — fires callback when ready
        ...
        manager.stop()
    """

    def __init__(self, status_callback: Optional[Callable[[bool, str], None]] = None):
        """
        Args:
            status_callback: Called with (is_connected: bool, message: str) when 
                             Tor status changes (bootstrap progress, errors, etc.)
        """
        self._process = None          # stem.process handle
        self._tor_path: Optional[str] = None
        self._connected = False
        self._status_callback = status_callback
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        """Start Tor in a background thread so the UI doesn't block."""
        self._thread = threading.Thread(target=self._launch_tor, daemon=True)
        self._thread.start()

    def stop(self):
        """Terminate the Tor process gracefully."""
        if self._process is not None:
            try:
                self._process.kill()
                logger.info("Tor process terminated.")
            except Exception as e:
                logger.warning(f"Error stopping Tor: {e}")
        self._connected = False

    # ------------------------------------------------------------------
    # Internal launch logic
    # ------------------------------------------------------------------

    def _emit_status(self, connected: bool, message: str):
        self._connected = connected
        if self._status_callback:
            self._status_callback(connected, message)

    def _launch_tor(self):
        """Attempt to launch Tor and wait for bootstrap."""
        try:
            from stem.process import launch_tor_with_config
            from stem import Signal
            import stem.control
        except ImportError:
            self._emit_status(False, "stem library not installed. Run: pip install stem")
            return

        tor_path = find_tor_executable()
        if tor_path is None:
            self._emit_status(
                False,
                "Tor executable not found.\n"
                "Please install Tor from https://www.torproject.org/download/ "
                "and ensure it is in your PATH or a standard install location.",
            )
            return

        self._tor_path = tor_path
        self._emit_status(False, "Starting Tor... (this may take 10-30 seconds)")

        try:
            # We use a dedicated data directory to cache consensus/state,
            # which drastically speeds up subsequent startups.
            data_dir = os.path.join(os.path.dirname(__file__), ".tor_data")
            os.makedirs(data_dir, exist_ok=True)

            self._process = launch_tor_with_config(
                tor_cmd=tor_path,
                config={
                    "SocksPort": str(TOR_SOCKS_PORT),
                    "ControlPort": str(TOR_CONTROL_PORT),
                    "DataDirectory": data_dir,
                    "Log": "notice stdout",
                    # 🚀 Speed optimizations for faster startup:
                    "StrictNodes": "0",          # Don't fail if preferred nodes are down
                    "UseEntryGuards": "1",       # Cache entry guards to avoid re-building first hop
                    "AvoidDiskWrites": "0",      # Actually write the cache to disk
                    "UseMicrodescriptors": "1",  # Download smaller consensus files
                },
                init_msg_handler=self._handle_bootstrap_message,
                take_ownership=True,
            )
            # If launch_tor_with_config returns without raising, bootstrap succeeded.
            self._emit_status(True, "Tor connected — all traffic is encrypted and anonymised.")

        except OSError as e:
            self._emit_status(False, f"Tor process error: {e}")
        except Exception as e:
            self._emit_status(False, f"Tor failed to start: {e}")

    def _handle_bootstrap_message(self, line: str):
        """
        Callback invoked by stem for each line of Tor output.
        Used to relay progress messages to the UI and console.
        """
        logger.info(f"[Tor] {line}")
        if "Bootstrapped" in line:
            # Extract percentage if present, e.g. "Bootstrapped 80% (conn_dir)"
            try:
                percent = int(line.split("Bootstrapped")[1].split("%")[0].strip())
                self._emit_status(False, f"Tor bootstrapping… {percent}%")
            except (IndexError, ValueError):
                self._emit_status(False, f"Tor: {line.strip()}")
