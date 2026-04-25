"""
updater.py
----------
BroanyX Browser — Auto-Update Checker

Runs in a background thread on startup.
Fetches version.json from GitHub, compares with current version,
and emits a Qt signal if an update is available so the UI can
show a non-intrusive notification banner.

GitHub release URL pattern:
  version.json  → https://raw.githubusercontent.com/Broanyx/BroanyX-browser/main/version.json
  installer     → https://github.com/Broanyx/BroanyX-browser/releases/latest/download/BroanyX-Setup.exe
"""

import logging
import threading
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# ── Current app version (bump this on every release) ───────────────────────
APP_VERSION = "1.0.0"

# ── Where to check for updates ─────────────────────────────────────────────
VERSION_CHECK_URL = (
    "https://raw.githubusercontent.com/Broanyx/BroanyX-browser/main/version.json"
)

# Timeout for the HTTP request (seconds)
REQUEST_TIMEOUT = 8


def _version_tuple(v: str):
    """Convert '1.2.3' → (1, 2, 3) for easy comparison."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


class UpdateChecker(QObject):
    """
    Emits update_available(latest_version, download_url, release_notes)
    on the Qt main thread when a newer version is found.
    """

    update_available = pyqtSignal(str, str, str)  # version, url, notes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[threading.Thread] = None

    def check_async(self):
        """Start background update check (non-blocking)."""
        self._thread = threading.Thread(
            target=self._check,
            daemon=True,
            name="update-checker",
        )
        self._thread.start()

    def _check(self):
        """Background thread: fetch version.json and compare."""
        try:
            import requests  # already in requirements.txt

            logger.info(f"Checking for updates at {VERSION_CHECK_URL} …")
            resp = requests.get(VERSION_CHECK_URL, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            data = resp.json()
            latest_version = data.get("version", "0.0.0")
            download_url = data.get(
                "url",
                "https://github.com/Broanyx/BroanyX-browser/releases/latest",
            )
            release_notes = data.get("notes", "")

            if _version_tuple(latest_version) > _version_tuple(APP_VERSION):
                logger.info(
                    f"Update available: {APP_VERSION} → {latest_version}"
                )
                # Emit signal — Qt will deliver it on the main thread
                self.update_available.emit(latest_version, download_url, release_notes)
            else:
                logger.info(f"BroanyX is up to date (v{APP_VERSION}).")

        except requests.exceptions.ConnectionError:
            logger.debug("Update check skipped — no internet connection.")
        except requests.exceptions.Timeout:
            logger.debug("Update check timed out.")
        except Exception as e:
            logger.warning(f"Update check failed: {e}")
