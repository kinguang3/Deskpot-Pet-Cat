# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""记忆模块

轻量级记忆系统，使用现有 Storage 保存互动信息。
记录：
- last_interaction_time
- today_interaction_count
- total_interaction_count
- last_sleep_time
- last_wake_time
- last_position
"""

import time
from datetime import datetime

from src.core.event_bus import EventBus
from src.utils.storage import Storage
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Memory:
    """Nina 的轻量记忆。

    使用 Storage (JSON) 持久化关键互动数据。
    """

    def __init__(self, storage: Storage):
        self._storage = storage
        self._event_bus = EventBus()

        # 内存缓存
        self._data: dict = {}

        # 加载记忆
        self._load()

        logger.debug("Memory initialized")

    def _load(self):
        """从 Storage 加载记忆。"""
        self._data = self._storage.load("pet_memory")
        logger.debug("Memory loaded: %d entries", len(self._data))

    def _save(self):
        """保存记忆到 Storage。"""
        self._storage.save(self._data, "pet_memory")

    # ─── 互动记录 ───

    def record_interaction(self):
        """记录一次用户互动。"""
        now = time.time()
        today = datetime.now().strftime("%Y-%m-%d")

        # 更新最后互动时间
        self._data["last_interaction_time"] = now

        # 更新总互动次数
        self._data["total_interaction_count"] = (
            self._data.get("total_interaction_count", 0) + 1
        )

        # 更新今日互动次数（检查是否跨天）
        last_date = self._data.get("last_interaction_date", "")
        if last_date != today:
            self._data["today_interaction_count"] = 1
            self._data["last_interaction_date"] = today
        else:
            self._data["today_interaction_count"] = (
                self._data.get("today_interaction_count", 0) + 1
            )

        # 定期保存（每10次互动保存一次，避免频繁写磁盘）
        total = self._data["total_interaction_count"]
        if total % 10 == 0:
            self._save()

        logger.debug(
            "Interaction recorded (today: %d, total: %d)",
            self._data["today_interaction_count"],
            self._data["total_interaction_count"],
        )

    def record_sleep(self):
        """记录进入睡眠。"""
        self._data["last_sleep_time"] = time.time()
        self._save()
        logger.debug("Sleep recorded")

    def record_wake(self):
        """记录醒来。"""
        self._data["last_wake_time"] = time.time()
        self._save()
        logger.debug("Wake recorded")

    def record_position(self, x: int, y: int):
        """记录窗口位置。"""
        self._data["last_position"] = {"x": x, "y": y}
        # 位置变化不频繁保存

    # ─── 读取记忆 ───

    def get_last_interaction_time(self) -> float:
        """获取最后互动时间（时间戳）。"""
        return self._data.get("last_interaction_time", 0)

    def get_seconds_since_interact(self) -> float:
        """获取距上次互动的秒数。"""
        last = self.get_last_interaction_time()
        if last == 0:
            return 0
        return time.time() - last

    def get_today_interaction_count(self) -> int:
        """获取今日互动次数。"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._data.get("last_interaction_date") != today:
            return 0
        return self._data.get("today_interaction_count", 0)

    def get_total_interaction_count(self) -> int:
        """获取总互动次数。"""
        return self._data.get("total_interaction_count", 0)

    def get_last_sleep_time(self) -> float:
        """获取最后睡眠时间。"""
        return self._data.get("last_sleep_time", 0)

    def get_last_wake_time(self) -> float:
        """获取最后醒来时间。"""
        return self._data.get("last_wake_time", 0)

    def get_last_position(self) -> tuple[int, int] | None:
        """获取最后记录的位置。"""
        pos = self._data.get("last_position")
        if pos:
            return (pos.get("x", 0), pos.get("y", 0))
        return None

    # ─── 调试 ───

    def get_debug_info(self) -> dict:
        """获取调试信息。"""
        return {
            "total_interactions": self.get_total_interaction_count(),
            "today_interactions": self.get_today_interaction_count(),
            "seconds_since_interact": round(self.get_seconds_since_interact(), 1),
            "last_sleep": self._data.get("last_sleep_time", 0),
            "last_wake": self._data.get("last_wake_time", 0),
        }

    def save(self):
        """手动保存（退出时调用）。"""
        self._save()
