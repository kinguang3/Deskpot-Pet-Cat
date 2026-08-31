# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""行为状态定义

定义 Nina 的各种行为状态：
- Idle: 待机
- Walk: 行走
- Stop: 停留张望
- Sleep: 睡觉
- Typing: 跟随用户打字
- Watch: 注视/好奇
- Clicked: 被点击后的反应
- Dragged: 被拖动中
"""

import random
from PySide6.QtCore import QTimer

from src.behavior.state_machine import State
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class IdleState(State):
    """待机状态。Nina 静坐，等待行为控制器决策。"""

    def __init__(self):
        super().__init__("idle", priority=0)
        self._event_bus = EventBus()

    def enter(self):
        self._machine.anim.play("idle")

    def exit(self):
        pass


class WalkState(State):
    """行走状态。Nina 随机向左或向右走。"""

    def __init__(self):
        super().__init__("walk", priority=1)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._event_bus = EventBus()
        self._direction_right = True

    def enter(self):
        self._direction_right = random.random() < 0.5
        anim = "walk_right" if self._direction_right else "walk_left"
        self._machine.anim.play(anim)

        direction = "right" if self._direction_right else "left"
        self._event_bus.emit("behavior.walk_started", {"direction": direction})

        from src.behavior.controller import DEFAULT_WALK_MIN, DEFAULT_WALK_MAX
        delay = random.randint(DEFAULT_WALK_MIN, DEFAULT_WALK_MAX)
        self._timer.start(delay)

    def exit(self):
        self._timer.stop()
        self._event_bus.emit("behavior.walk_ended", {})

    def _on_timeout(self):
        if self._machine:
            self._machine.transition_to("idle")


class StopState(State):
    """停留状态。Nina 停下来张望，短暂亦留后回到 idle。"""

    def __init__(self):
        super().__init__("stop", priority=1)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def enter(self):
        self._machine.anim.play("idle")
        from src.behavior.controller import DEFAULT_STOP_MIN, DEFAULT_STOP_MAX
        delay = random.randint(DEFAULT_STOP_MIN, DEFAULT_STOP_MAX)
        self._timer.start(delay)

    def exit(self):
        self._timer.stop()

    def _on_timeout(self):
        if self._machine:
            self._machine.transition_to("idle")


class SleepState(State):
    """睡觉状态。Nina 进入睡眠，仅用户互动可唤醒。"""

    def __init__(self):
        super().__init__("sleep", priority=3)

    def enter(self):
        self._machine.anim.play("sleep", loop=True)

    def exit(self):
        pass

    def can_transition_to(self, target: str) -> bool:
        # 仅允许被点击唤醒或回到 idle
        return target in ("idle", "clicked")


class WatchState(State):
    """注视状态。Nina 好奇地看着什么。"""

    def __init__(self):
        super().__init__("watch", priority=1)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def enter(self):
        self._machine.anim.play("watching", loop=True)
        from src.behavior.controller import DEFAULT_WATCH_MIN, DEFAULT_WATCH_MAX
        delay = random.randint(DEFAULT_WATCH_MIN, DEFAULT_WATCH_MAX)
        self._timer.start(delay)

    def exit(self):
        self._timer.stop()

    def _on_timeout(self):
        if self._machine:
            self._machine.transition_to("idle")


class TypingState(State):
    """打字状态。Nina 跟随用户输入打字。"""

    def __init__(self):
        super().__init__("typing", priority=2)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def enter(self):
        self._machine.anim.play("typing", loop=True)
        self._timer.start(5000)

    def exit(self):
        self._timer.stop()

    def _on_timeout(self):
        if self._machine:
            self._machine.transition_to("idle")


class ClickedState(State):
    """被点击状态。Nina 被点击后有短暂反应。"""

    def __init__(self):
        super().__init__("clicked", priority=4)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def enter(self):
        self._machine.anim.play("watching")
        self._timer.start(1500)

    def exit(self):
        self._timer.stop()

    def _on_timeout(self):
        if self._machine:
            self._machine.transition_to("idle")


class DraggedState(State):
    """被拖动状态。Nina 被拖动时显示特殊动画。"""

    def __init__(self):
        super().__init__("dragged", priority=5)

    def enter(self):
        self._machine.anim.play("watching")

    def can_transition_to(self, target: str) -> bool:
        return True
