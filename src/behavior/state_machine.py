"""行为状态机模块

通用有限状态机引擎。
管理状态、转换条件、优先级。
"""

from typing import Callable
from PySide6.QtCore import QObject, Signal

from src.core.event_bus import EventBus


class State:
    """状态基类。"""

    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority
        self._machine = None

    def set_machine(self, machine):
        self._machine = machine

    def enter(self):
        """进入状态时调用。"""
        pass

    def exit(self):
        """退出状态时调用。"""
        pass

    def update(self, dt: float):
        """每帧更新。dt 为毫秒。"""
        pass

    def can_transition_to(self, target: str) -> bool:
        """是否允许转换到目标状态。子类可重写。"""
        return True


class StateMachine(QObject):
    """有限状态机。

    管理状态注册、切换、更新。
    """

    state_changed = Signal(str, str)  # (old_state, new_state)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_bus = EventBus()
        self._states: dict[str, State] = {}
        self._current: State = None
        self._previous_name: str = ""

    @property
    def current_state_name(self) -> str:
        return self._current.name if self._current else ""

    @property
    def previous_state_name(self) -> str:
        return self._previous_name

    def add_state(self, state: State):
        """注册一个状态。"""
        state.set_machine(self)
        self._states[state.name] = state

    def set_initial_state(self, name: str):
        """设置初始状态并进入。"""
        if name not in self._states:
            print(f"[StateMachine] State not found: {name}")
            return
        self._current = self._states[name]
        self._current.enter()
        self._event_bus.emit("state.entered", {"state": name})

    def transition_to(self, name: str) -> bool:
        """切换到指定状态。

        Returns:
            是否成功切换
        """
        if name not in self._states:
            print(f"[StateMachine] State not found: {name}")
            return False

        if self._current and self._current.name == name:
            return False

        target = self._states[name]

        if self._current and not self._current.can_transition_to(name):
            return False

        old_name = self._current.name if self._current else ""

        if self._current:
            self._current.exit()

        self._previous_name = old_name
        self._current = target
        self._current.enter()

        self.state_changed.emit(old_name, name)
        self._event_bus.emit("state.changed", {
            "from": old_name,
            "to": name,
        })

        return True

    def update(self, dt: float):
        """每帧更新当前状态。"""
        if self._current:
            self._current.update(dt)

    def is_state(self, name: str) -> bool:
        """当前是否处于指定状态。"""
        return self._current is not None and self._current.name == name
