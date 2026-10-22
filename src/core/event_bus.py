# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""事件总线模块

模块间通过事件通信，避免直接引用。
支持事件发送、监听。
跨线程安全：子线程 emit 的事件通过队列调度到主线程执行，用
``QCoreApplication.postEvent`` 立即唤醒事件循环，而不是固定间隔轮询
（此前每 10ms 轮询一次空队列，让主线程每秒白醒 100 次）。
"""

import queue
import threading
from collections import defaultdict
from typing import Callable

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 自定义事件类型：唤醒主线程排空队列（registerEventType 保证全局唯一）
_DRAIN_EVENT_TYPE = QEvent.Type(QEvent.registerEventType())


class _DrainEvent(QEvent):
    """队列存在待处理事件时的唤醒标记（轻量，无载荷）。"""

    def __init__(self):
        super().__init__(_DRAIN_EVENT_TYPE)


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
        self._pending: queue.Queue = queue.Queue()

        # 标记是否已有唤醒事件待处理，避免高频 emit 时排空事件堆积
        self._drain_scheduled = False

        # 唤醒兜底：正常路径 postEvent 立即送达；万一投递不可用
        # （QCoreApplication 尚未创建等），最迟 250ms 也会送达。
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._drain_queue)
        self._poll_timer.start(250)

        logger.debug("EventBus initialized (postEvent wake + 250ms fallback)")

    def on(self, event: str, callback: Callable):
        """监听事件。"""
        self._listeners[event].append(callback)

    def emit(self, event: str, data: dict = None):
        """发送事件。

        主线程直接执行；子线程放入队列并用排空事件唤醒主线程。
        """
        if data is None:
            data = {}

        if threading.current_thread().ident == self._main_thread_id:
            self._call_listeners(event, data)
            return

        self._pending.put((event, data))
        # postEvent 线程安全；事件按总线对象所属线程（主线程）投递。
        if not self._drain_scheduled:
            self._drain_scheduled = True
            app = QCoreApplication.instance()
            if app is not None:
                QCoreApplication.postEvent(self, _DrainEvent())

    def event(self, e: QEvent) -> bool:
        """处理排空请求（Qt 事件回调，主线程）。"""
        if e.type() == _DRAIN_EVENT_TYPE:
            self._drain_queue()
            return True
        return super().event(e)

    def _drain_queue(self):
        """从队列取出所有待处理事件并执行（主线程）。"""
        self._drain_scheduled = False
        while True:
            try:
                event, data = self._pending.get_nowait()
            except queue.Empty:
                break
            self._call_listeners(event, data)

    def _call_listeners(self, event: str, data: dict):
        """实际执行回调（主线程）。"""
        # .get 而非下标：未监听的事件名不再往 defaultdict 塞空列表
        for callback in self._listeners.get(event, ()):
            try:
                callback(data)
            except Exception:
                logger.exception("Error in listener for '%s'", event)
