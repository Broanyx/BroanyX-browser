"""
tab_widget.py
-------------
A custom QTabWidget with:
- "+" new-tab button embedded in the tab bar
- Per-tab close buttons
- Middle-click to close
- Favicon display per tab
- Smooth styling via the app stylesheet
"""

from PyQt6.QtWidgets import QTabWidget, QTabBar, QPushButton, QWidget, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QColor
import logging

logger = logging.getLogger(__name__)


class PhantomTabBar(QTabBar):
    """Custom tab bar with middle-click-to-close."""

    middle_clicked = pyqtSignal(int)   # tab index

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            idx = self.tabAt(event.pos())
            if idx >= 0:
                self.middle_clicked.emit(idx)
        super().mouseReleaseEvent(event)


class PhantomTabWidget(QTabWidget):
    """
    Enhanced tab widget with new-tab button and custom tab bar.
    Signals:
        new_tab_requested()  — user clicked the "+" button
        tab_close_requested(int) — close this tab index
    """

    new_tab_requested = pyqtSignal()
    tab_close_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Use our custom tab bar
        self._tab_bar = PhantomTabBar(self)
        self._tab_bar.middle_clicked.connect(self.tab_close_requested.emit)
        self.setTabBar(self._tab_bar)

        # Tab close buttons
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.tab_close_requested.emit)

        # Movable tabs (drag to reorder)
        self.setMovable(True)

        # Stretch to fill horizontal space
        self.setDocumentMode(True)

        # "+" button at the end of the tab bar
        self._new_tab_btn = QPushButton("+")
        self._new_tab_btn.setFixedSize(28, 28)
        self._new_tab_btn.setToolTip("Open new tab (Ctrl+T)")
        self._new_tab_btn.setObjectName("newTabButton")
        self._new_tab_btn.clicked.connect(self.new_tab_requested.emit)
        self.setCornerWidget(self._new_tab_btn, Qt.Corner.TopRightCorner)

    def update_tab_title(self, index: int, title: str):
        """Truncate long titles and update the tab label."""
        if 0 <= index < self.count():
            short = title[:28] + "…" if len(title) > 28 else title
            self.setTabText(index, short or "New Tab")
            self.setTabToolTip(index, title)

    def update_tab_icon(self, index: int, icon: QIcon):
        """Update favicon for the given tab."""
        if 0 <= index < self.count():
            self.setTabIcon(index, icon)
