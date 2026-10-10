# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""透明窗口模块

创建无边框、透明背景、始终显示的桌面窗口。
支持拖动移动。
"""

from PySide6.QtWidgets import QMainWindow, QWidget
from PySide6.QtCore import Qt, QPoint
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

    鼠标事件一律经 EventBus 的 ``window.*`` 事件外发，不在窗口类上定义
    Qt 信号：交互翻译层（interaction/mouse.py）与 Pet 都按事件名订阅，
    再堆信号只会多一条无人连接的通道。
    """

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

    def set_scale(self, scale: float):
        self._scale = max(0.5, min(2.0, scale))
        new_w = int(self._base_width * self._scale)
        new_h = int(self._base_height * self._scale)

        # 获取当前窗口几何（包含边框）
        geo = self.geometry()
        center_x = geo.x() + geo.width() / 2
        center_y = geo.y() + geo.height() / 2

        # 计算新位置（使中心对齐）
        new_x = int(center_x - new_w / 2)
        new_y = int(center_y - new_h / 2)

        # 一次性设置几何，避免中间状态闪烁
        self.setGeometry(new_x, new_y, new_w, new_h)

    def set_always_on_top(self, on_top: bool):
        """设置窗口是否始终置顶。

        修改 windowFlags 会让窗口隐藏，必须重新 show() 才生效。
        几何信息在换 flag 时会被 Qt 保留，这里仍显式恢复一次位置，
        避免在部分平台上出现窗口跳回 (0, 0)。
        """
        flags = self.windowFlags()
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        if flags == self.windowFlags():
            return
        was_visible = self.isVisible()
        geo = self.geometry()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()
            self.setGeometry(geo)

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
            event.accept()

            self._event_bus.emit(
                "window.mouse_released",
                {
                    "x": self.pos().x(),
                    "y": self.pos().y(),
                },
            )

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """处理鼠标双击。"""
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
