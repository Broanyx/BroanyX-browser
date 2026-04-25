"""
main.py
-------
BroanyX Browser — Entry Point

Bootstrap sequence:
  1. Create QApplication
  2. Load dark-mode stylesheet
  3. Create an off-the-record QWebEngineProfile (no disk persistence)
  4. Apply privacy settings (proxy, UA, cookies, WebRTC)
  5. Init AdBlockInterceptor + RequestInterceptor
  6. Plug RequestInterceptor into the profile
  7. Launch TorManager in background thread
  8. Show BrowserWindow
  9. Register Tor callbacks to update UI on main thread
 10. Enter Qt event loop

Run:
    python main.py
"""

import sys
import os
import logging

# ── App version (bump this on every release) ────────────────────────────────
APP_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-7s]  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phantom")

# ---------------------------------------------------------------------------
# Ensure PyQt6 Qt plugins are found (sometimes needed on Windows)
# ---------------------------------------------------------------------------
# Add the virtual environment's Qt plugin path
_venv_qt_plugins = os.path.join(
    os.path.dirname(sys.executable), "Lib", "site-packages", "PyQt6", "Qt6", "plugins"
)
if os.path.isdir(_venv_qt_plugins):
    os.environ.setdefault("QT_PLUGIN_PATH", _venv_qt_plugins)

# ---------------------------------------------------------------------------
# PyQt6 WebEngine MUST be imported BEFORE QApplication is created.
# This includes both QtWebEngineCore AND QtWebEngineWidgets — importing
# only Core is not enough; Widgets triggers the OpenGL context setup.
# ---------------------------------------------------------------------------
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView   # ← must be here, not inside main()
from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QPainter, QFont, QIcon

# ---------------------------------------------------------------------------
# App icon — loaded once and shared
# ---------------------------------------------------------------------------
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
_ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")
_PNG_PATH = os.path.join(ASSETS_DIR, "icon.png")


def _app_icon() -> QIcon:
    """Return the BroanyX app icon (ICO preferred, PNG fallback)."""
    for path in (_ICO_PATH, _PNG_PATH):
        if os.path.isfile(path):
            return QIcon(path)
    # Fallback: emoji-based icon
    px = QPixmap(256, 256)
    px.fill(QColor("#0a0a12"))
    return QIcon(px)


def _load_stylesheet() -> str:
    """Load the QSS stylesheet from assets/style.qss."""
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    if os.path.isfile(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    logger.warning("Stylesheet not found — using default Qt style.")
    return ""


def _make_splash() -> QSplashScreen:
    """Create a styled splash screen."""
    w, h = 480, 280
    pixmap = QPixmap(w, h)
    pixmap.fill(QColor("#0a0a12"))

    painter = QPainter(pixmap)

    # Background gradient
    from PyQt6.QtGui import QLinearGradient
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor("#0a0a12"))
    grad.setColorAt(1, QColor("#1a0a2e"))
    painter.fillRect(0, 0, w, h, grad)

    # Border
    from PyQt6.QtGui import QPen
    painter.setPen(QPen(QColor("#7c3aed"), 2))
    painter.drawRoundedRect(1, 1, w - 2, h - 2, 12, 12)

    # Title
    font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#e0e0ff"))
    painter.drawText(0, 60, w, 60, Qt.AlignmentFlag.AlignCenter, "🛡️ BroanyX Browser")

    # Subtitle
    font2 = QFont("Segoe UI", 13)
    painter.setFont(font2)
    painter.setPen(QColor("#a855f7"))
    painter.drawText(0, 120, w, 40, Qt.AlignmentFlag.AlignCenter, "Privacy-First · Tor-Routed · Ad-Free")

    # Loading text
    font3 = QFont("Segoe UI", 10)
    painter.setFont(font3)
    painter.setPen(QColor("#8080aa"))
    painter.drawText(0, 190, w, 30, Qt.AlignmentFlag.AlignCenter, "Initializing Tor & ad-block rules…")

    painter.end()
    splash = QSplashScreen(pixmap)
    return splash


class _TorSignalBridge(QObject):
    """
    A tiny QObject that lives on the main thread and emits a Qt signal
    when the Tor background thread calls update().  This is the correct
    PyQt6 pattern for thread-safe cross-thread UI updates (Q_ARG is
    not available in PyQt6).
    """
    status_changed = pyqtSignal(bool, str)


def main():
    # ── 1. QApplication ────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("BroanyX Browser")
    app.setOrganizationName("BroanyX")
    app.setApplicationVersion(APP_VERSION)

    # Set app-wide icon (shows in taskbar, alt-tab, window chrome)
    icon = _app_icon()
    app.setWindowIcon(icon)

    # ── 2. Stylesheet ───────────────────────────────────────────────────
    qss = _load_stylesheet()
    if qss:
        app.setStyleSheet(qss)

    # ── 3. Splash screen ────────────────────────────────────────────────
    splash = _make_splash()
    splash.show()
    app.processEvents()

    # ── 4. WebEngine Profile (off-the-record = no disk persistence) ─────
    logger.info("Creating off-the-record WebEngine profile…")
    profile = QWebEngineProfile(parent=None)
    # Note: passing no name to constructor creates a unique non-default profile.
    # Use off_the_record programmatically after construction:
    # PyQt6 doesn't expose a direct "create off-the-record" constructor,
    # so we use a named profile but enforce NoPersistentCookies.

    # ── 5. Privacy settings ─────────────────────────────────────────────
    from privacy_settings import apply_privacy_settings
    logger.info("Applying privacy settings…")
    apply_privacy_settings(profile, tor_host="127.0.0.1", tor_port=9050)

    # ── 6. Ad blocker ───────────────────────────────────────────────────
    from adblocker import AdBlockInterceptor, RequestInterceptor
    logger.info("Initializing ad-blocker (loading rules in background)…")
    ad_blocker = AdBlockInterceptor()
    interceptor = RequestInterceptor(ad_blocker)
    profile.setUrlRequestInterceptor(interceptor)

    # ── 7. Tor manager ──────────────────────────────────────────────────
    from tor_manager import TorManager
    logger.info("Starting Tor daemon…")
    tor_manager = TorManager()  # callback wired after window is created

    # ── 8. Browser window ───────────────────────────────────────────────
    from browser_window import BrowserWindow
    logger.info("Opening browser window…")
    window = BrowserWindow(profile, interceptor, tor_manager)
    window.setWindowIcon(icon)

    # ── 9. Tor callback → UI update (thread-safe signal bridge) ────────
    _tor_bridge = _TorSignalBridge()
    _tor_bridge.status_changed.connect(window.update_tor_status)

    def _tor_status_callback(connected: bool, message: str):
        """
        Called from the Tor background thread.
        Emitting a Qt signal is the PyQt6-safe way to cross the thread
        boundary — Qt queues the call onto the main event loop automatically.
        """
        logger.info(f"Tor status: connected={connected}  msg={message}")
        _tor_bridge.status_changed.emit(connected, message)

    tor_manager._status_callback = _tor_status_callback
    tor_manager.start()

    # ── 10. Auto-update checker (non-blocking background thread) ────────
    from updater import UpdateChecker
    _updater = UpdateChecker()
    _updater.update_available.connect(window.show_update_banner)
    _updater.check_async()

    # ── 11. Close splash and show window ────────────────────────────────
    QTimer.singleShot(1800, lambda: [splash.finish(window), window.show()])

    # ── 11. Event loop ──────────────────────────────────────────────────
    exit_code = app.exec()

    # Cleanup
    tor_manager.stop()
    logger.info("BroanyX Browser exited cleanly.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
