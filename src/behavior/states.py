"""行为状态定义

定义 Nina 的各种行为状态：
- Idle: 待机
- Walk: 行走
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


class IdleState(State):
    """待机状态。Nina 静坐，随机决定下一步行为。"""

    def __init__(self):
        super().__init__("idle", priority=0)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._event_bus = EventBus()

    def enter(self):
        self._machine.anim.play("idle")
        delay = random.randint(3000, 8000)
        self._timer.start(delay)

    def exit(self):
        self._timer.stop()

    def _on_timeout(self):
        if not self._machine:
            return
        roll = random.random()
        if roll < 0.4:
            self._machine.transition_to("walk")
        elif roll < 0.55:
            self._machine.transition_to("watch")
        else:
            self._machine.transition_to("idle")


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

        # 通知行为管理器移动宠物
        self._event_bus.emit(
            "behavior.walk_started",
            {
                "direction": "right" if self._direction_right else "left",
            },
        )

        delay = random.randint(2000, 5000)
        self._timer.start(delay)

    def exit(self):
        self._timer.stop()
        self._event_bus.emit("behavior.walk_ended", {})

    def _on_timeout(self):
        if self._machine:
            self._machine.transition_to("idle")


class SleepState(State):
    """睡觉状态。Nina 进入睡眠。"""

    def __init__(self):
        super().__init__("sleep", priority=3)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def enter(self):
        self._machine.anim.play("sleep", loop=True)
        # 睡觉持续较长时间
        self._timer.start(30000)

    def exit(self):
        self._timer.stop()

    def _on_timeout(self):
        if self._machine:
            self._machine.transition_to("idle")

    def can_transition_to(self, target: str) -> bool:
        # 被点击时可以醒来
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
        self._timer.start(3000)

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
        # 打字状态持续到用户停止输入或超时
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
        # 播放 watching 作为点击反应
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
