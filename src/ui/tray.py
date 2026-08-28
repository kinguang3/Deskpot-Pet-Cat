"""系统托盘模块

管理系统托盘图标和菜单。
"""

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Signal, QObject

from src.core.event_bus import EventBus


class SystemTray(QObject):
    """系统托盘管理器。"""

    show_requested = Signal()
    hide_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_bus = EventBus()
        self._tray = QSystemTrayIcon(parent)
        self._menu = QMenu()

        self._setup_icon()
        self._setup_menu()

        self._tray.activated.connect(self._on_activated)

    def _setup_icon(self):
        """创建托盘图标。"""
        # 生成一个简单的猫爪图标
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 画一个简单的猫爪形状
        painter.setBrush(QColor(255, 180, 100))
        painter.setPen(QColor(200, 140, 70))
        painter.drawEllipse(16, 28, 32, 30)  # 掌心
        painter.drawEllipse(10, 14, 16, 16)  # 左上趾
        painter.drawEllipse(26, 8, 14, 14)  # 中上趾
        painter.drawEllipse(40, 14, 16, 16)  # 右上趾

        painter.end()

        icon = QIcon(pixmap)
        self._tray.setIcon(icon)
        self._tray.setToolTip("GBC Nina")

    def _setup_menu(self):
        """创建托盘菜单。"""
        self._menu.addAction("显示 Nina", self._on_show)
        self._menu.addAction("隐藏 Nina", self._on_hide)
        self._menu.addSeparator()
        self._menu.addAction("设置", self._on_settings)
        self._menu.addSeparator()
        self._menu.addAction("退出", self._on_quit)

        self._tray.setContextMenu(self._menu)

    def show(self):
        """显示托盘图标。"""
        self._tray.show()

    def hide(self):
        """隐藏托盘图标。"""
        self._tray.hide()

    def show_message(self, title: str, message: str):
        """显示托盘通知。"""
        self._tray.showMessage(title, message)

    def _on_activated(self, reason):
        """处理托盘图标点击。"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_show()

    def _on_show(self):
        self.show_requested.emit()
        self._event_bus.emit("tray.show_clicked", {})

    def _on_hide(self):
        self.hide_requested.emit()
        self._event_bus.emit("tray.hide_clicked", {})

    def _on_settings(self):
        self.settings_requested.emit()
        self._event_bus.emit("tray.settings_clicked", {})

    def _on_quit(self):
        self.quit_requested.emit()
        self._event_bus.emit("tray.quit_clicked", {})
