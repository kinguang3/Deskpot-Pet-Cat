# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""事件总线模块

模块间通过事件通信，避免直接引用。
支持事件发送、监听、一次性监听。
"""

import threading
from collections import defaultdict
from typing import Callable, Any

from PySide6.QtCore import QTimer, QThread

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EventBus:
    """轻量级事件总线，支持跨线程安全调用。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            _instance = super().__new__(cls)
            _instance._main_thread_id = threading.main_thread().ident
            cls._instance = _instance
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._listeners: dict[str, list[Callable]] = defaultdict(list)
        self._once_listeners: dict[str, list[Callable]] = defaultdict(list)
        logger.debug("EventBus initialized")

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

        如果当前不在主线程，会调度到主线程执行回调。
        """
        if data is None:
            data = {}

        # 检查是否在主线程
        current_thread = threading.current_thread().ident
        is_main = current_thread == self._main_thread_id

        logger.debug(
            "EventBus.emit [%s] thread=%s is_main=%s listeners=%d",
            event,
            threading.current_thread().name,
            is_main,
            len(self._listeners[event]),
        )

        if is_main:
            # 主线程直接执行
            self._call_listeners(event, data)
        else:
            # 子线程调度到主线程
            logger.debug("EventBus.emit [%s] scheduling to main thread", event)
            QTimer.singleShot(0, lambda e=event, d=data: self._call_listeners(e, d))

    def _call_listeners(self, event: str, data: dict):
        """实际执行回调（应在主线程调用）。"""
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
