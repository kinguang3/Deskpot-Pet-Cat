# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""鼠标交互模块

处理用户鼠标操作，将原始事件转化为语义化事件。
"""

import time

from PySide6.QtCore import QObject, QTimer, Qt

from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MouseInteraction(QObject):
    """管理鼠标交互逻辑。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_bus = EventBus()

        self._click_count: int = 0
        self._double_click_threshold: float = 0.3  # 秒

        self._last_interact_time: float = time.time()
        self._inactive_threshold: float = 300  # 5 分钟无交互进入睡觉

        # 单击要等一个双击窗口再发：双击的第二击在 Qt 里是
        # MouseButtonDblClick（不会再发一次 press），因此这里把单击暂攒着，
        # 短延迟内收到双击就取消，否则一次双击会同时触发点击反应和打字。
        self._pending_click: dict | None = None
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._emit_pending_single_click)

        # 监听窗口事件
        self._event_bus.on("window.mouse_pressed", self._on_mouse_pressed)
        self._event_bus.on("window.double_clicked", self._on_double_clicked)
        self._event_bus.on("window.mouse_entered", self._on_mouse_entered)
        self._event_bus.on("window.mouse_left", self._on_mouse_left)

        logger.debug(
            "MouseInteraction initialized (inactive threshold: %ds)",
            self._inactive_threshold,
        )

    @property
    def seconds_since_interact(self) -> float:
        return time.time() - self._last_interact_time

    def _on_mouse_pressed(self, data: dict):
        # 注意：不能用 `== 1` / `== 2` 判断按钮。PySide6 6.x 的
        # Qt.MouseButton 是枚举，和 int 比较恒为 False（实测 LeftButton == 1
        # -> False），会让左键/右键彻底失效，只剩双击能用。
        button = data.get("button")
        self._last_interact_time = time.time()

        if button == Qt.MouseButton.LeftButton:
            self._pending_click = data
            self._click_timer.start(
                int(self._double_click_threshold * 1000)
            )
        elif button == Qt.MouseButton.RightButton:
            self._event_bus.emit("interaction.right_click", data)

    def _emit_pending_single_click(self):
        """双击窗口已过，把暂攒的单击发出去。"""
        data = self._pending_click
        self._pending_click = None
        if data is not None:
            self._event_bus.emit("interaction.single_click", data)

    def _on_double_clicked(self, data: dict):
        # 取消刚要发出的单击，避免双击同时触发两套反应
        self._click_timer.stop()
        self._pending_click = None
        self._last_interact_time = time.time()
        self._event_bus.emit("interaction.double_click", data)

    def _on_mouse_entered(self, data: dict):
        self._last_interact_time = time.time()
        self._event_bus.emit("interaction.hover_enter", data)

    def _on_mouse_left(self, data: dict):
        self._event_bus.emit("interaction.hover_leave", data)

    def check_inactive(self) -> bool:
        """检查是否长时间无交互。"""
        return self.seconds_since_interact > self._inactive_threshold
