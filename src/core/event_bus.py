# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""事件总线模块

模块间通过事件通信，避免直接引用。
支持事件发送、监听、一次性监听。
跨线程安全：子线程 emit 的事件通过队列 + QTimer 调度到主线程执行。
"""

import queue
import threading
from collections import defaultdict
from typing import Callable

from PySide6.QtCore import QTimer, QObject

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EventBus(QObject):
    """轻量级事件总线，支持跨线程安全调用。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            obj = super().__new__(cls)
            obj._main_thread_id = threading.main_thread().ident
            cls._instance = obj
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        super().__init__()
        self._initialized = True
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        self._once_listeners: dict[str, list[Callable]] = defaultdict(list)
        self._pending: queue.Queue = queue.Queue()

        # 主线程定时器，每 10ms 检查队列
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._drain_queue)
        self._poll_timer.start(10)

        logger.debug("EventBus initialized")

    def on(self, event: str, callback: Callable):
        """监听事件。"""
        self._listeners[event].append(callback)

    def once(self, event: str, callback: Callable):
        """一次性监听事件。触发后自动移除。"""
        self._once_listeners[event].append(callback)

    def off(self, event: str, callback: Callable = None):
        """取消监听。"""
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

        主线程直接执行；子线程放入队列由 QTimer 调度到主线程。
        """
        if data is None:
            data = {}

        current_thread = threading.current_thread().ident
        is_main = current_thread == self._main_thread_id

        if is_main:
            self._call_listeners(event, data)
        else:
            self._pending.put((event, data))

    def _drain_queue(self):
        """从队列取出所有待处理事件并执行（主线程 QTimer 回调）。"""
        while not self._pending.empty():
            try:
                event, data = self._pending.get_nowait()
            except queue.Empty:
                break
            self._call_listeners(event, data)

    def _call_listeners(self, event: str, data: dict):
        """实际执行回调（主线程）。"""
        for callback in self._listeners[event]:
            try:
                callback(data)
            except Exception:
                logger.exception("Error in listener for '%s'", event)

        for callback in self._once_listeners[event]:
            try:
                callback(data)
            except Exception:
                logger.exception("Error in once-listener for '%s'", event)
        self._once_listeners[event].clear()
