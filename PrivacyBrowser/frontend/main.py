"""
main.py
-------
PrivacyBrowser — Hybrid Architecture Entry Point

Bootstrap sequence:
  1. QApplication
  2. Dark-mode stylesheet
  3. QWebEngineProfile (no disk persistence)
  4. Privacy settings → route ALL traffic through Go proxy (127.0.0.1:8080)
  5. Launch ProxyManager (Go backend) in background thread
  6. Launch TorManager (Tor daemon) in background thread
  7. Build BrowserWindow
  8. Wire thread-safe Qt signal bridges for status updates
  9. Show window after splash
 10. Event loop

Run:
    python main.py
"""

import sys
import os
import logging

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-7s]  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("privacybrowser")

# ── Ensure Qt plugins are found on Windows ───────────────────────────────────
_venv_qt_plugins = os.path.join(
    os.path.dirname(sys.executable), "Lib", "site-packages", "PyQt6", "Qt6", "plugins"
)
if os.path.isdir(_venv_qt_plugins):
    os.environ.setdefault("QT_PLUGIN_PATH", _venv_qt_plugins)

# ── PyQt6 WebEngine MUST be imported before QApplication ─────────────────────
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView   # triggers OpenGL setup
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QPainter, QFont, QPen, QLinearGradient


# ─────────────────────────────────────────────────────────────────────────────
# Splash screen
# ─────────────────────────────────────────────────────────────────────────────

def _make_splash() -> QSplashScreen:
    w, h = 520, 300
    pixmap = QPixmap(w, h)
    pixmap.fill(QColor("#0a0a12"))

    painter = QPainter(pixmap)

    # Background gradient
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor("#0d0d1f"))
    grad.setColorAt(1, QColor("#1a0a2e"))
    painter.fillRect(0, 0, w, h, grad)

    # Glow border
    for thickness, alpha in [(4, 40), (2, 100), (1, 200)]:
        pen = QPen(QColor(124, 58, 237, alpha), thickness)
        painter.setPen(pen)
        painter.drawRoundedRect(
            thickness // 2, thickness // 2,
            w - thickness, h - thickness, 14, 14
        )

    # Title
    font = QFont("Segoe UI", 30, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#e0e0ff"))
    painter.drawText(0, 50, w, 70, Qt.AlignmentFlag.AlignCenter, "🛡️ PrivacyBrowser")

    # Architecture tag
    font2 = QFont("Segoe UI", 11, QFont.Weight.Medium)
    painter.setFont(font2)
    painter.setPen(QColor("#a855f7"))
    painter.drawText(0, 118, w, 30, Qt.AlignmentFlag.AlignCenter,
                     "Python · Go Proxy · Tor · Ad-Block")

    # Status line
    font3 = QFont("Segoe UI", 9)
    painter.setFont(font3)
    painter.setPen(QColor("#6060aa"))
    painter.drawText(0, 200, w, 24, Qt.AlignmentFlag.AlignCenter,
                     "Starting Go proxy engine & Tor daemon…")

    # Chain diagram
    font4 = QFont("Segoe UI", 8)
    painter.setFont(font4)
    painter.setPen(QColor("#4a4a6a"))
    painter.drawText(0, 236, w, 20, Qt.AlignmentFlag.AlignCenter,
                     "Browser → Go Proxy (:8080) → Tor (:9050) → Internet")

    painter.end()
    return QSplashScreen(pixmap)


# ─────────────────────────────────────────────────────────────────────────────
# Thread-safe signal bridges (Qt signals are safe across threads)
# ─────────────────────────────────────────────────────────────────────────────

class _TorSignalBridge(QObject):
    """Bridges TorManager background thread → main Qt thread."""
    status_changed = pyqtSignal(bool, str)


class _ProxySignalBridge(QObject):
    """Bridges ProxyManager background thread → main Qt thread."""
    status_changed = pyqtSignal(bool, str)


# ─────────────────────────────────────────────────────────────────────────────
# Stylesheet loader
# ─────────────────────────────────────────────────────────────────────────────

def _load_stylesheet() -> str:
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "style.qss")
    if os.path.isfile(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    logger.warning("Stylesheet not found — using default Qt style.")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── 1. QApplication ────────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setApplicationName("PrivacyBrowser")
    app.setOrganizationName("PrivacyBrowser")
    app.setApplicationVersion("2.0.0")

    # ── 2. Stylesheet ───────────────────────────────────────────────────────
    qss = _load_stylesheet()
    if qss:
        app.setStyleSheet(qss)

    # ── 3. Splash screen ────────────────────────────────────────────────────
    splash = _make_splash()
    splash.show()
    app.processEvents()

    # ── 4. WebEngine Profile (no persistent disk storage) ───────────────────
    logger.info("Creating WebEngine profile…")
    profile = QWebEngineProfile(parent=None)

    # ── 5. Privacy settings → route via Go proxy ────────────────────────────
    from privacy_settings import apply_privacy_settings
    logger.info("Applying privacy settings (proxy = Go engine @ 127.0.0.1:8080)…")
    apply_privacy_settings(profile, proxy_host="127.0.0.1", proxy_port=8080)

    # ── 6. Go Proxy Manager ─────────────────────────────────────────────────
    from proxy_manager import ProxyManager
    logger.info("Starting Go proxy engine…")
    proxy_manager = ProxyManager()

    # ── 7. Tor Manager ──────────────────────────────────────────────────────
    from tor_manager import TorManager
    logger.info("Starting Tor daemon…")
    tor_manager = TorManager()

    # ── 8. Browser Window ───────────────────────────────────────────────────
    from browser_window import BrowserWindow
    logger.info("Creating browser window…")
    window = BrowserWindow(profile, tor_manager, proxy_manager)

    # ── 9. Thread-safe signal bridges ───────────────────────────────────────
    _tor_bridge   = _TorSignalBridge()
    _proxy_bridge = _ProxySignalBridge()

    _tor_bridge.status_changed.connect(window.update_tor_status)
    _proxy_bridge.status_changed.connect(window.update_proxy_status)

    def _on_tor_status(connected: bool, message: str):
        logger.info(f"Tor: connected={connected}  msg={message!r}")
        _tor_bridge.status_changed.emit(connected, message)

    def _on_proxy_status(running: bool, message: str):
        logger.info(f"Proxy: running={running}  msg={message!r}")
        _proxy_bridge.status_changed.emit(running, message)

    tor_manager._status_callback   = _on_tor_status
    proxy_manager._status_callback = _on_proxy_status

    # ── 10. Launch background services ──────────────────────────────────────
    proxy_manager.start()   # Go proxy first (Tor routes through it)
    tor_manager.start()     # Tor daemon second

    # ── 11. Show window after splash delay ──────────────────────────────────
    QTimer.singleShot(2000, lambda: [splash.finish(window), window.show()])

    # ── 12. Event loop ──────────────────────────────────────────────────────
    exit_code = app.exec()

    # Cleanup (also called from closeEvent, but belt-and-suspenders)
    tor_manager.stop()
    proxy_manager.stop()
    logger.info("PrivacyBrowser exited cleanly.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
