"""
browser_window.py
-----------------
Main application window for BroanyX Browser.

Contains:
- Navigation toolbar (back, forward, refresh, home, stop)
- URL bar with padlock icon and Tor/HTTPS indicators
- tabbed browsing via PhantomTabWidget
- Tor status pill (live updates from TorManager)
- Ad-block counter in status bar
- Page load progress bar
- Keyboard shortcuts
- Settings menu (JS toggle, ad-block toggle, clear cache/cookies)
"""

import logging
import os
from typing import Optional

from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import (
    QAction, QIcon, QKeySequence, QPixmap, QColor, QPainter, QFont
)
from PyQt6.QtWidgets import (
    QMainWindow, QToolBar, QLineEdit, QProgressBar,
    QStatusBar, QLabel, QWidget, QHBoxLayout,
    QVBoxLayout, QSizePolicy, QApplication, QMessageBox,
    QMenu
)
from PyQt6.QtWebEngineCore import QWebEngineProfile

from tab_widget import PhantomTabWidget
from web_view import PhantomWebView

logger = logging.getLogger(__name__)

HOME_URL = "https://duckduckgo.com"
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def _make_icon_from_text(text: str, color: str = "#e0e0ff", size: int = 24) -> QIcon:
    """Create a QIcon from a Unicode emoji/text character."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    font = QFont("Segoe UI Emoji", int(size * 0.65))
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)


class BrowserWindow(QMainWindow):
    """
    The main BroanyX Browser window.
    
    Args:
        profile:     The shared QWebEngineProfile (with privacy settings applied)
        interceptor: RequestInterceptor (ad-blocker) instance
        tor_manager: TorManager instance
    """

    def __init__(self, profile: QWebEngineProfile, interceptor, tor_manager):
        super().__init__()
        self._profile = profile
        self._interceptor = interceptor
        self._tor_manager = tor_manager

        self.setWindowTitle("BroanyX Browser 🛡️")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self._build_ui()
        self._connect_signals()
        self._load_shortcuts()

        # Timer to update ad-block counter every 2s
        self._counter_timer = QTimer(self)
        self._counter_timer.timeout.connect(self._update_ad_counter)
        self._counter_timer.start(2000)

        # Open a first tab
        self.open_new_tab(HOME_URL)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self):
        """Assemble all UI components."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Update notification banner (hidden by default)
        self._update_banner = self._build_update_banner()
        self._update_banner.hide()
        layout.addWidget(self._update_banner)

        # Progress bar (thin, at very top)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
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
        """Build the navigation toolbar widget (not QToolBar — custom QWidget for styling)."""
        bar = QWidget()
        bar.setObjectName("navBar")
        bar.setFixedHeight(52)
        bar.setStyleSheet("""
            QWidget#navBar {
                background-color: #12121e;
                border-bottom: 1px solid #2e2e4e;
            }
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        # Navigation buttons
        self._btn_back = self._make_nav_btn("←", "Back (Alt+Left)")
        self._btn_forward = self._make_nav_btn("→", "Forward (Alt+Right)")
        self._btn_reload = self._make_nav_btn("↻", "Reload (F5)")
        self._btn_home = self._make_nav_btn("🏠", "Home")
        self._btn_stop = self._make_nav_btn("✕", "Stop loading")

        layout.addWidget(self._btn_back)
        layout.addWidget(self._btn_forward)
        layout.addWidget(self._btn_reload)
        layout.addWidget(self._btn_home)
        layout.addWidget(self._btn_stop)
        layout.addSpacing(4)

        # Padlock icon (HTTPS indicator)
        self._padlock_label = QLabel("🔒")
        self._padlock_label.setFixedWidth(24)
        self._padlock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._padlock_label.setToolTip("Secure connection")
        layout.addWidget(self._padlock_label)

        # URL bar
        self._url_bar = QLineEdit()
        self._url_bar.setPlaceholderText("  Enter URL or search term…")
        self._url_bar.setClearButtonEnabled(True)
        self._url_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._url_bar)

        # Tor status pill
        self._tor_label = QLabel("⏳ Tor Starting…")
        self._tor_label.setObjectName("torStatusLabel")
        self._tor_label.setObjectName("torStatusConnecting")
        self._tor_label.setStyleSheet("""
            QLabel {
                color: #f59e0b;
                background-color: #1c1107;
                border: 1px solid #f59e0b;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        self._tor_label.setToolTip("Tor anonymization status")
        layout.addWidget(self._tor_label)

        return bar

    def _make_nav_btn(self, text: str, tooltip: str):
        from PyQt6.QtWidgets import QPushButton
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 32)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #a0a0cc;
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 15px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #252540;
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

    def _build_update_banner(self) -> QWidget:
        """Build the update notification banner (hidden until an update is found)."""
        from PyQt6.QtWidgets import QPushButton
        banner = QWidget()
        banner.setObjectName("updateBanner")
        banner.setFixedHeight(38)
        banner.setStyleSheet("""
            QWidget#updateBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a0040, stop:1 #2d006e);
                border-bottom: 1px solid #7c3aed;
            }
        """)
        row = QHBoxLayout(banner)
        row.setContentsMargins(14, 4, 10, 4)
        row.setSpacing(10)

        self._update_icon = QLabel("🚀")
        row.addWidget(self._update_icon)

        self._update_text = QLabel("A new version of BroanyX is available!")
        self._update_text.setStyleSheet("color: #d8b4fe; font-size: 13px; font-weight: 600;")
        row.addWidget(self._update_text, 1)

        self._update_btn = QPushButton("Download Update")
        self._update_btn.setFixedHeight(26)
        self._update_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #9333ea; }
            QPushButton:pressed { background-color: #6d28d9; }
        """)
        self._update_download_url = ""
        self._update_btn.clicked.connect(
            lambda: self.open_new_tab(self._update_download_url) if self._update_download_url else None
        )
        row.addWidget(self._update_btn)

        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedSize(22, 22)
        dismiss_btn.setToolTip("Dismiss")
        dismiss_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8080aa;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover { color: #ffffff; }
        """)
        dismiss_btn.clicked.connect(banner.hide)
        row.addWidget(dismiss_btn)

        return banner

    @pyqtSlot(str, str, str)
    def show_update_banner(self, version: str, url: str, notes: str):
        """Called by UpdateChecker signal when a newer version is available."""
        self._update_download_url = url
        self._update_text.setText(
            f"BroanyX v{version} is available!  {('— ' + notes) if notes else ''}"
        )
        self._update_banner.show()
        logger.info(f"Update banner shown for v{version}")

    def _build_status_bar(self):
        """Populate the status bar with ad-block counter and URL tooltip."""
        self._status_url_label = QLabel("")
        self._status_url_label.setStyleSheet("color: #8080aa; font-size: 12px;")
        self._status_bar.addWidget(self._status_url_label, 1)

        self._ad_block_label = QLabel("🛡 Ads blocked: 0")
        self._ad_block_label.setObjectName("adBlockLabel")
        self._status_bar.addPermanentWidget(self._ad_block_label)

    def _build_menu_bar(self):
        """Build the application menu bar."""
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

        self._adblock_action = QAction("Ad Blocker Active", self, checkable=True)
        self._adblock_action.setChecked(True)
        self._adblock_action.triggered.connect(self._toggle_adblock)
        view_menu.addAction(self._adblock_action)

        view_menu.addSeparator()

        find_act = QAction("Find in Page\tCtrl+F", self)
        find_act.triggered.connect(self._open_find_bar)
        view_menu.addAction(find_act)

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

        clear_cookies_act = QAction("Clear Cookies & Cache", self)
        clear_cookies_act.triggered.connect(self._clear_browsing_data)
        privacy_menu.addAction(clear_cookies_act)

        privacy_menu.addSeparator()

        check_tor_act = QAction("Check Tor Connection (check.torproject.org)", self)
        check_tor_act.triggered.connect(
            lambda: self.open_new_tab("https://check.torproject.org")
        )
        privacy_menu.addAction(check_tor_act)

        # ── Help ──
        help_menu = menubar.addMenu("&Help")
        about_act = QAction("About BroanyX Browser", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ==================================================================
    # Signal Wiring
    # ==================================================================

    def _connect_signals(self):
        self._tabs.new_tab_requested.connect(lambda: self.open_new_tab(HOME_URL))
        self._tabs.tab_close_requested.connect(self._on_tab_close_requested)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._btn_back.clicked.connect(self._navigate_back)
        self._btn_forward.clicked.connect(self._navigate_forward)
        self._btn_reload.clicked.connect(self._reload_or_stop)
        self._btn_home.clicked.connect(lambda: self._current_view() and self._current_view().setUrl(QUrl(HOME_URL)))
        self._btn_stop.clicked.connect(lambda: self._current_view() and self._current_view().stop())

        self._url_bar.returnPressed.connect(self._navigate_to_url)

    def _load_shortcuts(self):
        from PyQt6.QtGui import QShortcut
        shortcuts = {
            "Ctrl+T": lambda: self.open_new_tab(HOME_URL),
            "Ctrl+W": self._close_current_tab,
            "Ctrl+L": self._focus_url_bar,
            "F5": lambda: self._current_view() and self._current_view().reload(),
            "Ctrl+R": lambda: self._current_view() and self._current_view().reload(),
            "Alt+Left": self._navigate_back,
            "Alt+Right": self._navigate_forward,
            "Ctrl++": self._zoom_in,
            "Ctrl+-": self._zoom_out,
            "Ctrl+0": self._zoom_reset,
            "Ctrl+F": self._open_find_bar,
        }
        for key, slot in shortcuts.items():
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(slot)

    # ==================================================================
    # Tab Management
    # ==================================================================

    def open_new_tab(self, url: str = HOME_URL, view: Optional[PhantomWebView] = None) -> PhantomWebView:
        """Open a new tab, optionally reusing an existing view (e.g., from popup)."""
        # Handle PyQt signal param pass-through (if connected without lambda)
        if isinstance(url, PhantomWebView):
            view = url
            url = HOME_URL

        if view is None:
            view = PhantomWebView(self._profile)
            view.setUrl(QUrl(url if url else HOME_URL))

        idx = self._tabs.addTab(view, "New Tab")
        self._tabs.setCurrentIndex(idx)

        # Wire per-tab signals
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
            # Don't close last tab — open a blank one first
            self.open_new_tab(HOME_URL)
        widget = self._tabs.widget(index)
        self._tabs.removeTab(index)
        if widget:
            widget.deleteLater()

    def _close_current_tab(self):
        self._on_tab_close_requested(self._tabs.currentIndex())

    def _on_tab_changed(self, index: int):
        """Update nav buttons and URL bar when switching tabs."""
        view = self._current_view()
        if view:
            self._url_bar.setText(view.url().toString())
            self._update_nav_buttons(view)

    # ==================================================================
    # Navigation
    # ==================================================================

    def _current_view(self) -> Optional[PhantomWebView]:
        w = self._tabs.currentWidget()
        return w if isinstance(w, PhantomWebView) else None

    def _navigate_to_url(self):
        raw = self._url_bar.text().strip()
        if not raw:
            return

        # Determine whether it's a URL or a search query
        if self._is_url(raw):
            if "://" not in raw:
                raw = "https://" + raw
            url = QUrl(raw)
        else:
            # DuckDuckGo search (privacy-respecting)
            from urllib.parse import quote_plus
            url = QUrl(f"https://duckduckgo.com/?q={quote_plus(raw)}")

        view = self._current_view()
        if view:
            view.setUrl(url)

    def _is_url(self, text: str) -> bool:
        """Heuristic: does this look like a URL rather than a search query?"""
        if text.startswith(("http://", "https://", "ftp://", "file://", "view-source:")):
            return True
        # Has a TLD-like suffix and no spaces
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

    # ==================================================================
    # Page load event handlers
    # ==================================================================

    def _on_url_changed(self, url: QUrl, view: PhantomWebView):
        if view == self._current_view():
            self._url_bar.setText(url.toString())
            # Update padlock based on scheme
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

    # ==================================================================
    # Tor status updates (called from TorManager thread via main thread)
    # ==================================================================

    @pyqtSlot(bool, str)
    def update_tor_status(self, connected: bool, message: str):
        """Called by TorManager callback — must run on main Qt thread."""
        if connected:
            self._tor_label.setText("🧅 Tor Active")
            self._tor_label.setStyleSheet("""
                QLabel {
                    color: #22c55e;
                    background-color: #052e16;
                    border: 1px solid #22c55e;
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 12px;
                    font-weight: 600;
                }
            """)
            self._tor_label.setToolTip(f"✅ Tor Connected\n{message}")
        elif "%" in message:
            # Still bootstrapping
            self._tor_label.setText(f"⏳ {message.split('…')[-1].strip() if '…' in message else 'Connecting…'}")
            self._tor_label.setStyleSheet("""
                QLabel {
                    color: #f59e0b;
                    background-color: #1c1107;
                    border: 1px solid #f59e0b;
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 12px;
                    font-weight: 600;
                }
            """)
            self._tor_label.setToolTip(f"⏳ Tor Bootstrapping\n{message}")
        else:
            # Error / not found
            self._tor_label.setText("⚠️ Tor Offline")
            self._tor_label.setStyleSheet("""
                QLabel {
                    color: #ef4444;
                    background-color: #1c0a0a;
                    border: 1px solid #ef4444;
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 12px;
                    font-weight: 600;
                }
            """)
            self._tor_label.setToolTip(f"❌ Tor Not Connected\n{message}")

    # ==================================================================
    # Ad-block counter
    # ==================================================================

    def _update_ad_counter(self):
        if self._interceptor and hasattr(self._interceptor, "_ad_blocker"):
            count = self._interceptor._ad_blocker.blocked_count
            self._ad_block_label.setText(f"🛡 Ads blocked: {count}")

    # ==================================================================
    # Settings actions
    # ==================================================================

    def _toggle_javascript(self, enabled: bool):
        from PyQt6.QtWebEngineCore import QWebEngineSettings
        self._profile.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, enabled
        )
        # Reload all tabs to apply
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, PhantomWebView):
                w.reload()

    def _toggle_adblock(self, enabled: bool):
        if hasattr(self._interceptor, "_ad_blocker"):
            self._interceptor._ad_blocker._ready = enabled
        self._status_bar.showMessage(
            "Ad Blocker enabled." if enabled else "Ad Blocker disabled.", 3000
        )

    def _open_find_bar(self):
        v = self._current_view()
        if v:
            v.page().findText("")  # focus the built-in find dialog if available
            # Qt WebEngine doesn't have a built-in bar; trigger JS find
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
            "Clear all cookies and cached data?\n\n"
            "This cannot be undone for the current session.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._profile.clearHttpCache()
            self._profile.cookieStore().deleteAllCookies()
            self._status_bar.showMessage("Cookies and cache cleared.", 3000)

    def _show_about(self):
        QMessageBox.information(
            self, "About BroanyX Browser",
            "🛡️ <b>BroanyX Browser</b> v1.0\n\n"
            "A privacy-first desktop browser.\n\n"
            "🧅 All traffic routes through Tor\n"
            "🚫 EasyList + EasyPrivacy ad blocking\n"
            "🔒 WebRTC & geolocation disabled\n"
            "🕵️ User-Agent spoofed\n\n"
            "Built with Python, PyQt6, and open-source privacy tools.",
        )

    # ==================================================================
    # Close event
    # ==================================================================

    def closeEvent(self, event):
        """Terminate Tor when the window is closed."""
        if self._tor_manager:
            self._tor_manager.stop()
        event.accept()
