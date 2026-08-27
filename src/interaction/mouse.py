"""鼠标交互模块

处理用户鼠标操作，将原始事件转化为语义化事件。
"""

import time

from PySide6.QtCore import QObject

from src.core.event_bus import EventBus


class MouseInteraction(QObject):
    """管理鼠标交互逻辑。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_bus = EventBus()

        self._last_click_time: float = 0
        self._click_count: int = 0
        self._double_click_threshold: float = 0.3  # 秒

        self._last_interact_time: float = time.time()
        self._inactive_threshold: float = 300  # 5 分钟无交互进入睡觉

        # 监听窗口事件
        self._event_bus.on("window.mouse_pressed", self._on_mouse_pressed)
        self._event_bus.on("window.double_clicked", self._on_double_clicked)
        self._event_bus.on("window.mouse_entered", self._on_mouse_entered)
        self._event_bus.on("window.mouse_left", self._on_mouse_left)

    @property
    def seconds_since_interact(self) -> float:
        return time.time() - self._last_interact_time

    def _on_mouse_pressed(self, data: dict):
        button = data.get("button")
        self._last_interact_time = time.time()

        if button == 1:  # 左键
            now = time.time()
            if now - self._last_click_time < self._double_click_threshold:
                self._click_count += 1
            else:
                self._click_count = 1
            self._last_click_time = now

            if self._click_count >= 2:
                self._event_bus.emit("interaction.double_click", data)
                self._click_count = 0
            else:
                # 延迟判断是否为单击（等待可能的双击）
                self._event_bus.emit("interaction.single_click", data)

        elif button == 2:  # 右键
            self._event_bus.emit("interaction.right_click", data)

    def _on_double_clicked(self, data: dict):
        self._last_interact_time = time.time()
        self._event_bus.emit("interaction.double_click", data)

    def _on_mouse_entered(self, data: dict):
        self._event_bus.emit("interaction.hover_enter", data)

    def _on_mouse_left(self, data: dict):
        self._event_bus.emit("interaction.hover_leave", data)

    def check_inactive(self) -> bool:
        """检查是否长时间无交互。"""
        return self.seconds_since_interact > self._inactive_threshold
