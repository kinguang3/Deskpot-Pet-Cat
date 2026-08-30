# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""透明窗口模块

创建无边框、透明背景、始终显示的桌面窗口。
支持拖动移动。
"""

from PySide6.QtWidgets import QMainWindow, QWidget
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QPixmap, QPainter, QMouseEvent

from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PetWindow(QMainWindow):
    """桌宠主窗口。

    特性：
    - 无边框
    - 透明背景
    - 始终置顶
    - 不在任务栏显示
    - 可拖动
    """

    # 自定义信号
    dragged = Signal(int, int)  # 拖动结束时发出 (x, y)
    clicked = Signal(QMouseEvent)  # 单击
    double_clicked = Signal(QMouseEvent)  # 双击

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_bus = EventBus()

        # 窗口标志：无边框 + 置顶 + 工具窗口（不显示在任务栏）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # 透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        # 拖动状态
        self._dragging = False
        self._drag_offset = QPoint()

        # 当前要绘制的帧
        self._current_pixmap: QPixmap = QPixmap()
        self._opacity: float = 0.95

        # 中心部件
        self._central = QWidget(self)
        self.setCentralWidget(self._central)

        self.setStyleSheet("background: transparent;")

        # 窗口默认配置
        self._base_width = 175
        self._base_height = 175
        self._scale = 1.0
        self.resize(
            int(self._base_width * self._scale),
            int(self._base_height * self._scale),
        )
        logger.debug(
            "Pet window created (base: %dx%d, scale: %.1f)",
            self._base_width,
            self._base_height,
            self._scale,
        )

    def set_frame(self, pixmap: QPixmap):
        """设置当前要绘制的精灵帧。"""
        self._current_pixmap = pixmap
        self.update()

    def set_opacity(self, opacity: float):
        """设置窗口透明度 (0.0 ~ 1.0)。"""
        self._opacity = max(0.0, min(1.0, opacity))
        self.setWindowOpacity(self._opacity)
        logger.debug("Window opacity set to %.2f", self._opacity)

    def set_scale(self, scale: float):
        self._scale = max(0.5, min(2.0, scale))
        new_w = int(self._base_width * self._scale)
        new_h = int(self._base_height * self._scale)
        self.resize(new_w, new_h)
        logger.debug("Window scale set to %.1f (%dx%d)", self._scale, new_w, new_h)

    def paintEvent(self, event):
        """绘制当前帧到窗口。"""
        if self._current_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self._current_pixmap)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        """处理鼠标按下 - 开始拖动。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            event.accept()

        self.clicked.emit(event)
        self._event_bus.emit(
            "window.mouse_pressed",
            {
                "button": event.button(),
                "x": event.position().x(),
                "y": event.position().y(),
            },
        )

    def mouseMoveEvent(self, event: QMouseEvent):
        """处理鼠标移动 - 拖动窗口。"""
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            self.move(new_pos)
            event.accept()

            self._event_bus.emit(
                "window.mouse_moved",
                {
                    "x": new_pos.x(),
                    "y": new_pos.y(),
                },
            )

    def mouseReleaseEvent(self, event: QMouseEvent):
        """处理鼠标释放 - 结束拖动。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.dragged.emit(self.pos().x(), self.pos().y())
            event.accept()
            logger.debug(
                "Window dragged to (%d, %d)", self.pos().x(), self.pos().y()
            )

            self._event_bus.emit(
                "window.mouse_released",
                {
                    "x": self.pos().x(),
                    "y": self.pos().y(),
                },
            )

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """处理鼠标双击。"""
        self.double_clicked.emit(event)
        self._event_bus.emit(
            "window.double_clicked",
            {
                "button": event.button(),
            },
        )

    def enterEvent(self, event):
        """鼠标进入窗口。"""
        self._event_bus.emit("window.mouse_entered", {})

    def leaveEvent(self, event):
        """鼠标离开窗口。"""
        self._event_bus.emit("window.mouse_left", {})

    def show_center(self):
        """在屏幕底部中间显示窗口。"""
        screen = self.screen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - self.width()) // 2
            y = screen_geo.height() - self.height() - 50
            self.move(x, y)
            logger.debug("Window centered at (%d, %d)", x, y)
