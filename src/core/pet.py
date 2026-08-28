"""宠物实体模块

管理 Nina 的位置、朝向、状态，以及与窗口和动画的协调。
"""

from PySide6.QtCore import QObject, QTimer, Signal

from src.core.event_bus import EventBus
from src.core.window import PetWindow
from src.animation.manager import AnimationManager


class Pet(QObject):
    """桌宠实体。

    职责：
    - 管理宠物的位置和朝向
    - 协调动画播放
    - 响应用户交互
    - 广播宠物状态事件
    """

    def __init__(
        self, window: PetWindow, anim_manager: AnimationManager, parent=None
    ):
        super().__init__(parent)
        self._window = window
        self._anim = anim_manager
        self._event_bus = EventBus()

        self._name: str = "Nina"
        self._facing_right: bool = True
        self._x: int = 0
        self._y: int = 0

        # 连接动画帧变化到窗口渲染
        self._anim.frame_changed.connect(self._on_frame_changed)

        # 监听窗口事件
        self._event_bus.on("window.mouse_pressed", self._on_mouse_pressed)
        self._event_bus.on("window.double_clicked", self._on_double_clicked)
        self._event_bus.on("window.mouse_entered", self._on_mouse_entered)
        self._event_bus.on("window.mouse_left", self._on_mouse_left)

    @property
    def name(self) -> str:
        return self._name

    @property
    def facing_right(self) -> bool:
        return self._facing_right

    def set_facing(self, right: bool):
        """设置朝向。"""
        self._facing_right = right

    def start(self):
        """启动宠物，开始播放 idle 动画。"""
        self._x = self._window.pos().x()
        self._y = self._window.pos().y()
        self._anim.play("idle")
        self._event_bus.emit("pet.started", {"name": self._name})

    def move_to(self, x: int, y: int):
        """移动到指定位置。"""
        self._x = x
        self._y = y
        self._window.move(x, y)
        self._event_bus.emit("pet.moved", {"x": x, "y": y})

    def _on_frame_changed(self, pixmap):
        """动画帧变化时更新窗口。"""
        self._window.set_frame(pixmap)

    def _on_mouse_pressed(self, data: dict):
        """响应鼠标点击。"""
        button = data.get("button")
        if button == 1:  # 左键
            self._event_bus.emit("pet.clicked", {"button": "left"})
        elif button == 2:  # 右键
            self._event_bus.emit("pet.clicked", {"button": "right"})

    def _on_double_clicked(self, data: dict):
        """响应双击。"""
        self._event_bus.emit("pet.double_clicked", data)

    def _on_mouse_entered(self, data: dict):
        """鼠标悬停。"""
        self._event_bus.emit("pet.hover_entered", data)

    def _on_mouse_left(self, data: dict):
        """鼠标离开。"""
        self._event_bus.emit("pet.hover_left", data)
