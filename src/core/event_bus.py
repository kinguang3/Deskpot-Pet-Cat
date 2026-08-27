"""事件总线模块

模块间通过事件通信，避免直接引用。
支持事件发送、监听、一次性监听。
"""

from collections import defaultdict
from typing import Callable, Any


class EventBus:
    """轻量级事件总线。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        self._once_listeners: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, callback: Callable):
        """监听事件。

        Args:
            event: 事件名称
            callback: 回调函数，接收 (data: dict) 参数
        """
        self._listeners[event].append(callback)

    def once(self, event: str, callback: Callable):
        """一次性监听事件。触发后自动移除。"""
        self._once_listeners[event].append(callback)

    def off(self, event: str, callback: Callable = None):
        """取消监听。

        如果不传 callback，移除该事件的所有监听器。
        """
        if callback is None:
            self._listeners[event].clear()
            self._once_listeners[event].clear()
        else:
            if callback in self._listeners[event]:
                self._listeners[event].remove(callback)
            if callback in self._once_listeners[event]:
                self._once_listeners[event].remove(callback)

    def emit(self, event: str, data: dict = None):
        """发送事件。

        Args:
            event: 事件名称
            data: 事件数据，传递给所有监听器
        """
        if data is None:
            data = {}

        for callback in self._listeners[event]:
            try:
                callback(data)
            except Exception as e:
                print(f"[EventBus] Error in listener for '{event}': {e}")

        for callback in self._once_listeners[event]:
            try:
                callback(data)
            except Exception as e:
                print(f"[EventBus] Error in once-listener for '{event}': {e}")
        self._once_listeners[event].clear()
