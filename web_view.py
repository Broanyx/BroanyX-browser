"""
web_view.py
-----------
Custom QWebEngineView subclass.

Handles:
- Permission requests (geo, notifications) — all denied
- New window / popup delegation back to the tab widget
- Context menu with privacy-aware items
- Page title / favicon change signals
"""

import logging
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, pyqtSignal, Qt
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction

from privacy_settings import deny_geo_permission

logger = logging.getLogger(__name__)

DEFAULT_HOME = "https://duckduckgo.com"


class PrivacyPage(QWebEnginePage):
    """
    Custom page that intercepts permission requests and
    handles new window creation internally.
    """

    new_window_requested = pyqtSignal(object)  # emits QWebEngineNewWindowRequest

    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(profile, parent)
        # Wire geolocation/permission denial
        self.featurePermissionRequested.connect(self._on_permission_requested)

    def _on_permission_requested(self, security_origin, feature):
        deny_geo_permission(self, security_origin, feature)

    def createWindow(self, win_type):  # noqa: N802
        """
        Called when JS calls window.open() or a link has target=_blank.
        We create a new WebView and return its page so Qt can populate it,
        then schedule adding it as a tab in the browser window.
        """
        new_view = PhantomWebView(self.profile())
        # Emit signal so BrowserWindow can add it as a tab
        # (We post-call via QTimer to avoid creating tabs during page load)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.new_window_requested.emit(new_view))
        return new_view.page()


class PhantomWebView(QWebEngineView):
    """
    The browser's main web view widget.
    One instance per tab.
    """

    # Emitted so the tab widget can update the tab title
    page_title_changed = pyqtSignal(str)
    # Emitted so tab widget can update favicon
    page_icon_changed = pyqtSignal(object)  # QIcon
    # Emitted when a new view should be opened as a tab
    new_tab_requested = pyqtSignal(object)  # PhantomWebView

    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(parent)

        # Use our custom page with privacy controls
        page = PrivacyPage(profile, self)
        self.setPage(page)

        # Connect signals
        self.titleChanged.connect(self.page_title_changed.emit)
        self.iconChanged.connect(self.page_icon_changed.emit)
        page.new_window_requested.connect(self._on_new_window)

        # Set a blank start page
        self.setUrl(QUrl(DEFAULT_HOME))

    def _on_new_window(self, new_view: "PhantomWebView"):
        self.new_tab_requested.emit(new_view)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a2e;
                color: #e0e0ff;
                border: 1px solid #4a4a6a;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #7c3aed;
            }
            QMenu::separator {
                height: 1px;
                background-color: #4a4a6a;
                margin: 4px 8px;
            }
        """)

        page = self.page()
        hit = page.contextMenuData()

        # Navigation actions
        back_action = QAction("← Back", self)
        back_action.setEnabled(self.history().canGoBack())
        back_action.triggered.connect(self.back)
        menu.addAction(back_action)

        forward_action = QAction("→ Forward", self)
        forward_action.setEnabled(self.history().canGoForward())
        forward_action.triggered.connect(self.forward)
        menu.addAction(forward_action)

        reload_action = QAction("↻ Reload", self)
        reload_action.triggered.connect(self.reload)
        menu.addAction(reload_action)

        menu.addSeparator()

        # Copy URL
        copy_url_action = QAction("📋 Copy Page URL", self)
        copy_url_action.triggered.connect(
            lambda: self._copy_to_clipboard(self.url().toString())
        )
        menu.addAction(copy_url_action)

        # Open link in new tab (if right-clicked on a link)
        if hit.linkUrl().isValid():
            open_tab_action = QAction("🔗 Open Link in New Tab", self)
            link_url = hit.linkUrl().toString()
            open_tab_action.triggered.connect(
                lambda: self.new_tab_requested.emit(self._make_child_view(link_url))
            )
            menu.addAction(open_tab_action)

            copy_link_action = QAction("📋 Copy Link URL", self)
            copy_link_action.triggered.connect(
                lambda: self._copy_to_clipboard(hit.linkUrl().toString())
            )
            menu.addAction(copy_link_action)

        menu.addSeparator()

        view_source_action = QAction("👁 View Page Source", self)
        view_source_action.triggered.connect(
            lambda: self.setUrl(QUrl("view-source:" + self.url().toString()))
        )
        menu.addAction(view_source_action)

        menu.exec(event.globalPos())

    def _copy_to_clipboard(self, text: str):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _make_child_view(self, url: str) -> "PhantomWebView":
        """Create a new view pre-loaded with a URL."""
        view = PhantomWebView(self.page().profile())
        view.setUrl(QUrl(url))
        return view
