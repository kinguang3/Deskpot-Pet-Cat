# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""自主行走位移模块

历史问题：`WalkState` 只播放 walk_left/walk_right 动画然后回到 idle，
从未真正修改窗口坐标；`behavior.walk_started` / `behavior.walk_ended`
事件也无人监听，`Pet.move_to()` 全项目零调用。结果是 Nina 只会在原地
"原地踏步"，设置里的「自动移动」勾选框形同虚设。

本模块补上缺失的位移逻辑：
- 监听 behavior.walk_started / behavior.walk_ended
- 按固定步长定时器逐帧推进窗口，并同步 Pet 朝向
- 位移被限制在 Nina 当前所在屏幕的可用区域内，不会走出屏幕
- 受 behavior.auto_move 开关控制

注意：drag / click / sleep 等状态下必须停止位移，否则会和用户的
拖拽操作抢窗口坐标。
"""

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QGuiApplication

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: 每次位移的像素数
STEP_PX = 4
#: 位移定时器间隔（毫秒）。4px / 60ms ≈ 67px/s，接近桌宠常见的缓慢踱步
STEP_INTERVAL_MS = 60
#: 到达屏幕边缘时是否折返
BOUNCE_AT_EDGE = True


class WalkMover(QObject):
    """把 walk 状态真正落到窗口坐标上。"""

    def __init__(self, pet, window, parent=None):
        super().__init__(parent)
        self._pet = pet
        self._window = window
        self._event_bus = EventBus()
        self._config = ConfigManager()

        self._auto_move = bool(
            self._config.get("behavior.auto_move", True)
        )

        self._direction = 1  # 1=right, -1=left
        self._moving = False

        self._timer = QTimer(self)
        self._timer.setInterval(STEP_INTERVAL_MS)
        self._timer.timeout.connect(self._step)

        self._event_bus.on("behavior.walk_started", self._on_walk_started)
        self._event_bus.on("behavior.walk_ended", self._on_walk_ended)
        self._event_bus.on("settings.changed", self._on_settings_changed)
        # 任何抢占窗口坐标的状态都必须立刻停下，避免和拖拽打架
        for evt in (
            "state.changed",
            "window.drag_started",
            "window.mouse_pressed",
        ):
            self._event_bus.on(evt, self._on_interrupting_state)

        logger.info(
            "WalkMover initialized (auto_move=%s)", self._auto_move
        )

    def _on_settings_changed(self, data: dict):
        """设置面板保存后热更新开关。"""
        if isinstance(data, dict) and "behavior.auto_move" in data:
            self.set_auto_move(bool(data["behavior.auto_move"]))

    @property
    def auto_move(self) -> bool:
        return self._auto_move

    def set_auto_move(self, enabled: bool):
        """设置开关。关闭时若正在行走则立即停下。"""
        enabled = bool(enabled)
        if enabled == self._auto_move:
            return
        self._auto_move = enabled
        if not enabled:
            self._stop()
        logger.info("WalkMover auto_move -> %s", enabled)

    def stop(self):
        """外部（如退出）调用停止。"""
        self._stop()

    # ─── 事件处理 ───

    def _on_walk_started(self, data: dict):
        if not self._auto_move:
            logger.debug("walk_started ignored: auto_move disabled")
            return
        if self._moving:
            return
        self._direction = 1 if data.get("direction") == "right" else -1
        self._pet.set_facing(self._direction > 0)
        self._moving = True
        self._timer.start()

    def _on_walk_ended(self, data: dict):
        self._stop()

    def _on_interrupting_state(self, data: dict):
        target = data.get("to")
        if target == "walk":
            # 由 _on_walk_started 负责启动，这里不干预
            return
        self._stop()

    def _stop(self):
        self._moving = False
        self._timer.stop()

    # ─── 位移 ───

    def _step(self):
        if not self._moving:
            self._stop()
            return

        geo = self._window.geometry()
        bounds = self._walkable_bounds(geo)
        if bounds is None:
            self._stop()
            return

        new_x = geo.x() + self._direction * STEP_PX
        left = bounds.left()
        right = bounds.right() - geo.width() + 1

        # 越界处理：折返并把坐标夹回边界内
        if new_x <= left:
            new_x = left
            if BOUNCE_AT_EDGE:
                self._turn(1)
        elif new_x >= right:
            new_x = right
            if BOUNCE_AT_EDGE:
                self._turn(-1)

        # 贴边且已折返，下一帧会自然转向；若左右都到不了（屏幕比窗口还窄）
        # 就停下，避免原地抖动
        if left >= right:
            self._stop()
            return

        if new_x != geo.x():
            self._pet.move_to(new_x, geo.y())

    def _turn(self, direction: int):
        """折返：更新移动方向并同步朝向。

        朝向必须跟着改，否则会出现「播放 walk_left 动画但实际向右走」。
        """
        self._direction = 1 if direction > 0 else -1
        self._pet.set_facing(self._direction > 0)

    def _walkable_bounds(self, geo):
        """取 Nina 当前所在屏幕的可用区域，支持多显示器。

        找不到屏幕时返回 None（此时不移动，安全优先）。
        """
        screen = None
        if geo.x() >= 0 or geo.y() >= 0:
            screen = QGuiApplication.screenAt(geo.center())
        if screen is None:
            screen = self._window.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry()
