"""记忆模块

轻量级记忆系统，使用 Storage 持久化互动信息。
只记录 App 实际会写入/读取的字段：
- last_interaction_time（最后互动时间，用于跨天统计）
- today_interaction_count / last_interaction_date（今日互动次数）
- total_interaction_count（总互动次数）
- last_wake_time（最近一次被唤醒）
"""

import time
from datetime import datetime

from src.utils.storage import Storage
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Memory:
    """Nina 的轻量记忆。

    使用 Storage (JSON) 持久化关键互动数据。
    """

    def __init__(self, storage: Storage):
        self._storage = storage

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

    def record_wake(self):
        """记录醒来。"""
        self._data["last_wake_time"] = time.time()
        self._save()
        logger.debug("Wake recorded")

    def save(self):
        """手动保存（退出时调用）。"""
        self._save()
