"""
browser_window.py
-----------------
Main application window for PrivacyBrowser.

Features:
- Navigation toolbar (back, forward, reload, home, stop)
- URL bar with padlock / security indicator
- Tabbed browsing via PhantomTabWidget
- Tor status pill (live updates from TorManager)
- Go Proxy status indicator
- Ad-block counter in status bar
- Page-load progress bar
- Keyboard shortcuts
- Settings menu (JS toggle, ad-block toggle, clear data)
"""

import logging
import os
from typing import Optional

from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import (
    QAction, QIcon, QKeySequence, QPixmap, QColor, QPainter, QFont, QPen
)
from PyQt6.QtWidgets import (
    QMainWindow, QToolBar, QLineEdit, QProgressBar,
    QStatusBar, QLabel, QWidget, QHBoxLayout,
    QVBoxLayout, QSizePolicy, QApplication, QMessageBox,
    QMenu, QPushButton
)
from PyQt6.QtWebEngineCore import QWebEngineProfile

from tab_widget import PhantomTabWidget
from web_view import PhantomWebView

logger = logging.getLogger(__name__)

HOME_URL = "https://duckduckgo.com"
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


class BrowserWindow(QMainWindow):
    """
    The main PrivacyBrowser window.

    Args:
        profile:       Shared QWebEngineProfile (privacy settings already applied)
        tor_manager:   TorManager instance
        proxy_manager: ProxyManager (Go backend) instance
    """

    def __init__(self, profile: QWebEngineProfile, tor_manager, proxy_manager):
        super().__init__()
        self._profile = profile
        self._tor_manager = tor_manager
        self._proxy_manager = proxy_manager

        self.setWindowTitle("PrivacyBrowser 🛡️")
        self.setMinimumSize(1100, 700)
        self.resize(1360, 840)

        self._build_ui()
        self._connect_signals()
        self._load_shortcuts()

        # Periodic ad-block stats refresh
        self._counter_timer = QTimer(self)
        self._counter_timer.timeout.connect(self._update_status_indicators)
        self._counter_timer.start(2000)

        self.open_new_tab(HOME_URL)

    # =========================================================================
    # UI Construction
    # =========================================================================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Thin progress bar at very top
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        self._progress_bar.setStyleSheet("""
            QProgressBar { background: #0a0a12; border: none; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #7c3aed, stop:1 #06b6d4); border-radius: 2px; }
        """)
        layout.addWidget(self._progress_bar)

        # Navigation toolbar
        self._nav_bar = self._build_nav_toolbar()
        layout.addWidget(self._nav_bar)

        # Tab widget
        self._tabs = PhantomTabWidget()
        layout.addWidget(self._tabs)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._build_status_bar()

        # Menu bar
        self._build_menu_bar()

    def _build_nav_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("navBar")
        bar.setFixedHeight(56)
        bar.setStyleSheet("""
            QWidget#navBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #16162a, stop:1 #0f0f1e);
                border-bottom: 1px solid #2a2a4a;
            }
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        # Navigation buttons
        self._btn_back    = self._make_nav_btn("←", "Back (Alt+Left)")
        self._btn_forward = self._make_nav_btn("→", "Forward (Alt+Right)")
        self._btn_reload  = self._make_nav_btn("↻", "Reload (F5)")
        self._btn_home    = self._make_nav_btn("🏠", "Home")
        self._btn_stop    = self._make_nav_btn("✕", "Stop loading")

        for btn in (self._btn_back, self._btn_forward, self._btn_reload,
                    self._btn_home, self._btn_stop):
            layout.addWidget(btn)

        layout.addSpacing(6)

        # Padlock / security indicator
        self._padlock_label = QLabel("🔒")
        self._padlock_label.setFixedWidth(26)
        self._padlock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._padlock_label.setToolTip("Secure connection")
        layout.addWidget(self._padlock_label)

        # URL bar
        self._url_bar = QLineEdit()
        self._url_bar.setPlaceholderText("  Enter URL or search…")
        self._url_bar.setClearButtonEnabled(True)
        self._url_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._url_bar.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e36;
                color: #e0e0ff;
                border: 1px solid #3a3a5a;
                border-radius: 18px;
                padding: 6px 14px;
                font-size: 13px;
                selection-background-color: #7c3aed;
            }
            QLineEdit:focus {
                border-color: #7c3aed;
                background-color: #22223a;
            }
        """)
        layout.addWidget(self._url_bar)

        layout.addSpacing(8)

        # Go proxy status pill
        self._proxy_label = self._make_status_pill("⚙️ Proxy…", "orange")
        self._proxy_label.setToolTip("Go proxy engine status")
        layout.addWidget(self._proxy_label)

        layout.addSpacing(4)

        # Tor status pill
        self._tor_label = self._make_status_pill("⏳ Tor Starting…", "orange")
        self._tor_label.setToolTip("Tor anonymization status")
        layout.addWidget(self._tor_label)

        return bar

    def _make_nav_btn(self, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(34, 34)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a0a0cc;
                border: 1px solid transparent;
                border-radius: 8px;
                font-size: 15px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #252545;
                color: #ffffff;
                border-color: #4a4a6a;
            }
            QPushButton:pressed {
                background-color: #7c3aed;
                color: #ffffff;
            }
            QPushButton:disabled {
                color: #3a3a5a;
            }
        """)
        return btn

    def _make_status_pill(self, text: str, color: str) -> QLabel:
        colors = {
            "orange": ("color: #f59e0b; background-color: #1c1107; border-color: #f59e0b;"),
            "green":  ("color: #22c55e; background-color: #052e16; border-color: #22c55e;"),
            "red":    ("color: #ef4444; background-color: #1c0a0a; border-color: #ef4444;"),
        }
        style_colors = colors.get(color, colors["orange"])
        label = QLabel(text)
        label.setStyleSheet(f"""
            QLabel {{
                {style_colors}
                border: 1px solid;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        return label

    def _build_status_bar(self):
        self._status_url_label = QLabel("")
        self._status_url_label.setStyleSheet("color: #8080aa; font-size: 12px;")
        self._status_bar.addWidget(self._status_url_label, 1)

        self._ad_block_label = QLabel("🛡 Ads blocked: 0")
        self._ad_block_label.setStyleSheet("""
            color: #a855f7; font-size: 12px; font-weight: 600;
            padding: 0 8px;
        """)
        self._status_bar.addPermanentWidget(self._ad_block_label)

        self._chain_label = QLabel("🔗 Chain: Browser → Go Proxy → Tor → Internet")
        self._chain_label.setStyleSheet("color: #4a6a8a; font-size: 11px; padding: 0 8px;")
        self._status_bar.addPermanentWidget(self._chain_label)

    def _build_menu_bar(self):
        menubar = self.menuBar()

        # ── File ──
        file_menu = menubar.addMenu("&File")

        new_tab_act = QAction("New Tab\tCtrl+T", self)
        new_tab_act.triggered.connect(lambda: self.open_new_tab(HOME_URL))
        file_menu.addAction(new_tab_act)

        close_tab_act = QAction("Close Tab\tCtrl+W", self)
        close_tab_act.triggered.connect(self._close_current_tab)
        file_menu.addAction(close_tab_act)

        file_menu.addSeparator()

        quit_act = QAction("Quit\tCtrl+Q", self)
        quit_act.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_act)

        # ── View ──
        view_menu = menubar.addMenu("&View")

        self._js_action = QAction("JavaScript Enabled", self, checkable=True)
        self._js_action.setChecked(True)
        self._js_action.triggered.connect(self._toggle_javascript)
        view_menu.addAction(self._js_action)

        view_menu.addSeparator()

        zoom_in_act = QAction("Zoom In\tCtrl++", self)
        zoom_in_act.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_act)

        zoom_out_act = QAction("Zoom Out\tCtrl+-", self)
        zoom_out_act.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_act)

        zoom_reset_act = QAction("Reset Zoom\tCtrl+0", self)
        zoom_reset_act.triggered.connect(self._zoom_reset)
        view_menu.addAction(zoom_reset_act)

        # ── Privacy ──
        privacy_menu = menubar.addMenu("🔒 &Privacy")

        clear_act = QAction("Clear Cookies & Cache", self)
        clear_act.triggered.connect(self._clear_browsing_data)
        privacy_menu.addAction(clear_act)

        privacy_menu.addSeparator()

        check_tor_act = QAction("Check Tor Connection (check.torproject.org)", self)
        check_tor_act.triggered.connect(
            lambda: self.open_new_tab("https://check.torproject.org")
        )
        privacy_menu.addAction(check_tor_act)

        whatismyip_act = QAction("Check My IP (whatismyip.com)", self)
        whatismyip_act.triggered.connect(
            lambda: self.open_new_tab("https://www.whatismyip.com")
        )
        privacy_menu.addAction(whatismyip_act)

        # ── Help ──
        help_menu = menubar.addMenu("&Help")
        about_act = QAction("About PrivacyBrowser", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # =========================================================================
    # Signal Wiring
    # =========================================================================

    def _connect_signals(self):
        self._tabs.new_tab_requested.connect(lambda: self.open_new_tab(HOME_URL))
        self._tabs.tab_close_requested.connect(self._on_tab_close_requested)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._btn_back.clicked.connect(self._navigate_back)
        self._btn_forward.clicked.connect(self._navigate_forward)
        self._btn_reload.clicked.connect(self._reload_or_stop)
        self._btn_home.clicked.connect(
            lambda: self._current_view() and self._current_view().setUrl(QUrl(HOME_URL))
        )
        self._btn_stop.clicked.connect(
            lambda: self._current_view() and self._current_view().stop()
        )
        self._url_bar.returnPressed.connect(self._navigate_to_url)

    def _load_shortcuts(self):
        from PyQt6.QtGui import QShortcut
        shortcuts = {
            "Ctrl+T":    lambda: self.open_new_tab(HOME_URL),
            "Ctrl+W":    self._close_current_tab,
            "Ctrl+L":    self._focus_url_bar,
            "F5":        lambda: self._current_view() and self._current_view().reload(),
            "Ctrl+R":    lambda: self._current_view() and self._current_view().reload(),
            "Alt+Left":  self._navigate_back,
            "Alt+Right": self._navigate_forward,
            "Ctrl++":    self._zoom_in,
            "Ctrl+-":    self._zoom_out,
            "Ctrl+0":    self._zoom_reset,
            "Ctrl+F":    self._open_find_bar,
        }
        for key, slot in shortcuts.items():
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(slot)

    # =========================================================================
    # Tab Management
    # =========================================================================

    def open_new_tab(
        self, url: str = HOME_URL, view: Optional[PhantomWebView] = None
    ) -> PhantomWebView:
        if isinstance(url, PhantomWebView):
            view = url
            url = HOME_URL

        if view is None:
            view = PhantomWebView(self._profile)
            view.setUrl(QUrl(url if url else HOME_URL))

        idx = self._tabs.addTab(view, "New Tab")
        self._tabs.setCurrentIndex(idx)

        view.page_title_changed.connect(
            lambda title, i=idx: self._tabs.update_tab_title(self._tabs.indexOf(view), title)
        )
        view.page_icon_changed.connect(
            lambda icon, v=view: self._tabs.update_tab_icon(self._tabs.indexOf(v), icon)
        )
        view.new_tab_requested.connect(self.open_new_tab)
        view.urlChanged.connect(lambda url, v=view: self._on_url_changed(url, v))
        view.loadStarted.connect(lambda v=view: self._on_load_started(v))
        view.loadProgress.connect(lambda p, v=view: self._on_load_progress(p, v))
        view.loadFinished.connect(lambda ok, v=view: self._on_load_finished(ok, v))
        view.page().linkHovered.connect(self._status_url_label.setText)

        return view

    def _on_tab_close_requested(self, index: int):
        if self._tabs.count() <= 1:
            self.open_new_tab(HOME_URL)
        widget = self._tabs.widget(index)
        self._tabs.removeTab(index)
        if widget:
            widget.deleteLater()

    def _close_current_tab(self):
        self._on_tab_close_requested(self._tabs.currentIndex())

    def _on_tab_changed(self, index: int):
        view = self._current_view()
        if view:
            self._url_bar.setText(view.url().toString())
            self._update_nav_buttons(view)

    # =========================================================================
    # Navigation
    # =========================================================================

    def _current_view(self) -> Optional[PhantomWebView]:
        w = self._tabs.currentWidget()
        return w if isinstance(w, PhantomWebView) else None

    def _navigate_to_url(self):
        raw = self._url_bar.text().strip()
        if not raw:
            return
        if self._is_url(raw):
            if "://" not in raw:
                raw = "https://" + raw
            url = QUrl(raw)
        else:
            from urllib.parse import quote_plus
            url = QUrl(f"https://duckduckgo.com/?q={quote_plus(raw)}")

        view = self._current_view()
        if view:
            view.setUrl(url)

    def _is_url(self, text: str) -> bool:
        if text.startswith(("http://", "https://", "ftp://", "file://", "view-source:")):
            return True
        if " " not in text and ("." in text or ".onion" in text):
            return True
        return False

    def _navigate_back(self):
        v = self._current_view()
        if v and v.history().canGoBack():
            v.back()

    def _navigate_forward(self):
        v = self._current_view()
        if v and v.history().canGoForward():
            v.forward()

    def _reload_or_stop(self):
        v = self._current_view()
        if v:
            v.reload()

    def _focus_url_bar(self):
        self._url_bar.setFocus()
        self._url_bar.selectAll()

    # =========================================================================
    # Page load handlers
    # =========================================================================

    def _on_url_changed(self, url: QUrl, view: PhantomWebView):
        if view == self._current_view():
            self._url_bar.setText(url.toString())
            scheme = url.scheme()
            if scheme == "https":
                self._padlock_label.setText("🔒")
                self._padlock_label.setToolTip("Secure HTTPS connection")
            elif scheme == "http":
                self._padlock_label.setText("⚠️")
                self._padlock_label.setToolTip("Insecure HTTP connection")
            else:
                self._padlock_label.setText("🌐")
                self._padlock_label.setToolTip(scheme)

    def _on_load_started(self, view: PhantomWebView):
        if view == self._current_view():
            self._progress_bar.setValue(0)
            self._progress_bar.show()
            self._btn_reload.setText("✕")
            self._btn_reload.setToolTip("Stop loading")

    def _on_load_progress(self, progress: int, view: PhantomWebView):
        if view == self._current_view():
            self._progress_bar.setValue(progress)

    def _on_load_finished(self, ok: bool, view: PhantomWebView):
        if view == self._current_view():
            self._progress_bar.hide()
            self._btn_reload.setText("↻")
            self._btn_reload.setToolTip("Reload (F5)")
            self._update_nav_buttons(view)

    def _update_nav_buttons(self, view: PhantomWebView):
        self._btn_back.setEnabled(view.history().canGoBack())
        self._btn_forward.setEnabled(view.history().canGoForward())

    # =========================================================================
    # Status pill updates
    # =========================================================================

    @pyqtSlot(bool, str)
    def update_tor_status(self, connected: bool, message: str):
        """Called from TorManager → signal bridge → main thread."""
        if connected:
            self._set_pill(self._tor_label, "🧅 Tor Active", "green",
                           f"✅ Tor Connected\n{message}")
        elif "%" in message:
            short = message.split("…")[-1].strip() if "…" in message else "Connecting…"
            self._set_pill(self._tor_label, f"⏳ {short}", "orange",
                           f"⏳ Tor Bootstrapping\n{message}")
        else:
            self._set_pill(self._tor_label, "⚠️ Tor Offline", "red",
                           f"❌ Tor Not Connected\n{message}")

    @pyqtSlot(bool, str)
    def update_proxy_status(self, running: bool, message: str):
        """Called from ProxyManager → signal bridge → main thread."""
        if running:
            self._set_pill(self._proxy_label, "⚙️ Proxy Active", "green",
                           f"✅ Go Proxy Running\n{message}")
        else:
            self._set_pill(self._proxy_label, "⚙️ Proxy Offline", "red",
                           f"❌ Go Proxy Not Running\n{message}")

    def _set_pill(self, label: QLabel, text: str, color: str, tooltip: str):
        palette = {
            "orange": ("color: #f59e0b; background-color: #1c1107; border-color: #f59e0b;"),
            "green":  ("color: #22c55e; background-color: #052e16; border-color: #22c55e;"),
            "red":    ("color: #ef4444; background-color: #1c0a0a; border-color: #ef4444;"),
        }
        style = palette.get(color, palette["orange"])
        label.setText(text)
        label.setStyleSheet(f"""
            QLabel {{
                {style}
                border: 1px solid;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        label.setToolTip(tooltip)

    def _update_status_indicators(self):
        """Periodic refresh of ad-block counter."""
        # Ad-block count comes from the Go proxy /__proxy_status if available
        # For now we poll a local counter (proxy tracks this server-side)
        try:
            import urllib.request, json
            with urllib.request.urlopen(
                "http://127.0.0.1:8080/__proxy_status", timeout=1
            ) as resp:
                data = json.loads(resp.read())
                count = data.get("blocked_count", 0)
                self._ad_block_label.setText(f"🛡 Ads blocked: {count}")
        except Exception:
            pass

    # =========================================================================
    # Settings actions
    # =========================================================================

    def _toggle_javascript(self, enabled: bool):
        from PyQt6.QtWebEngineCore import QWebEngineSettings
        self._profile.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, enabled
        )
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, PhantomWebView):
                w.reload()

    def _open_find_bar(self):
        v = self._current_view()
        if v:
            v.page().runJavaScript("window.find('')")

    def _zoom_in(self):
        v = self._current_view()
        if v:
            v.setZoomFactor(min(v.zoomFactor() + 0.1, 3.0))

    def _zoom_out(self):
        v = self._current_view()
        if v:
            v.setZoomFactor(max(v.zoomFactor() - 0.1, 0.25))

    def _zoom_reset(self):
        v = self._current_view()
        if v:
            v.setZoomFactor(1.0)

    def _clear_browsing_data(self):
        reply = QMessageBox.question(
            self, "Clear Browsing Data",
            "Clear all cookies and cached data?\n\nThis cannot be undone for the current session.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._profile.clearHttpCache()
            self._profile.cookieStore().deleteAllCookies()
            self._status_bar.showMessage("Cookies and cache cleared.", 3000)

    def _show_about(self):
        QMessageBox.information(
            self, "About PrivacyBrowser",
            "🛡️ <b>PrivacyBrowser</b> v2.0 — Hybrid Architecture\n\n"
            "⚙️ Go Proxy Engine (127.0.0.1:8080)\n"
            "   • EasyList ad-blocking\n"
            "   • All traffic forwarded through Tor\n\n"
            "🧅 Tor Daemon (127.0.0.1:9050)\n"
            "   • Full anonymisation + .onion support\n\n"
            "🔒 Privacy Hardening\n"
            "   • WebRTC minimised\n"
            "   • Geolocation denied\n"
            "   • Spoofed User-Agent\n"
            "   • No persistent cookies\n\n"
            "Built with Python, PyQt6, Go, and Tor.",
        )

    # =========================================================================
    # Close event
    # =========================================================================

    def closeEvent(self, event):
        if self._tor_manager:
            self._tor_manager.stop()
        if self._proxy_manager:
            self._proxy_manager.stop()
        event.accept()
