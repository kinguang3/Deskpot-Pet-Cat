# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""时间上下文模块

根据电脑本地时间判断时段，影响 Nina 的行为权重。
不强制行为，只调整概率。
"""

from datetime import datetime
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TimePeriod(Enum):
    """时段枚举。"""
    MORNING = "morning"      # 5:00 - 9:00
    DAY = "day"              # 9:00 - 17:00
    EVENING = "evening"      # 17:00 - 21:00
    NIGHT = "night"          # 21:00 - 1:00
    LATE_NIGHT = "late_night"  # 1:00 - 5:00


# 每个时段的行为权重修正系数
# >1.0 = 增加概率, <1.0 = 减少概率
TIME_MODIFIERS: dict[TimePeriod, dict[str, float]] = {
    TimePeriod.MORNING: {
        "walk": 1.4,      # 早上活跃
        "happy": 1.3,     # 心情好
        "watch": 1.1,
        "stop": 1.0,
        "idle": 0.7,      # 不太会 idle
        "sleep": 0.3,     # 不会睡觉
    },
    TimePeriod.DAY: {
        "walk": 1.0,      # 正常
        "happy": 1.0,
        "watch": 1.0,
        "stop": 1.0,
        "idle": 1.0,
        "sleep": 0.5,     # 白天不太睡
    },
    TimePeriod.EVENING: {
        "walk": 0.8,      # 晚上活动减少
        "happy": 0.9,
        "watch": 1.2,     # 好奇心高
        "stop": 1.1,
        "idle": 1.3,      # 更多 idle
        "sleep": 1.2,     # 开始困了
    },
    TimePeriod.NIGHT: {
        "walk": 0.5,      # 夜晚安静
        "happy": 0.7,
        "watch": 0.8,
        "stop": 0.9,
        "idle": 1.5,      # 大部分时间 idle
        "sleep": 1.8,     # 很容易睡
    },
    TimePeriod.LATE_NIGHT: {
        "walk": 0.2,      # 深夜几乎不动
        "happy": 0.5,
        "watch": 0.5,
        "stop": 0.5,
        "idle": 1.0,
        "sleep": 2.5,     # 强烈建议睡觉
    },
}


class TimeContext:
    """时间上下文管理器。

    根据当前时间返回时段和行为修正系数。
    """

    def __init__(self):
        self._current_period: TimePeriod = TimePeriod.DAY
        self._update()
        logger.debug("TimeContext initialized (period: %s)", self._current_period.value)

    @property
    def period(self) -> TimePeriod:
        """当前时段。"""
        self._update()
        return self._current_period

    @property
    def period_name(self) -> str:
        """当前时段名称。"""
        return self._current_period.value

    def _update(self):
        """更新当前时段。"""
        hour = datetime.now().hour

        if 5 <= hour < 9:
            new_period = TimePeriod.MORNING
        elif 9 <= hour < 17:
            new_period = TimePeriod.DAY
        elif 17 <= hour < 21:
            new_period = TimePeriod.EVENING
        elif hour >= 21 or hour < 1:
            new_period = TimePeriod.NIGHT
        else:  # 1 <= hour < 5
            new_period = TimePeriod.LATE_NIGHT

        if new_period != self._current_period:
            logger.info("Time period changed: %s -> %s", self._current_period.value, new_period.value)
            self._current_period = new_period

    def get_modifier(self, behavior: str) -> float:
        """获取某行为在当前时段的修正系数。

        Args:
            behavior: 行为名称

        Returns:
            修正系数（>1.0 增加, <1.0 减少）
        """
        modifiers = TIME_MODIFIERS.get(self._current_period, {})
        return modifiers.get(behavior, 1.0)

    def get_all_modifiers(self) -> dict[str, float]:
        """获取当前时段所有行为的修正系数。"""
        return dict(TIME_MODIFIERS.get(self._current_period, {}))

    def get_debug_info(self) -> dict:
        """获取调试信息。"""
        return {
            "period": self._current_period.value,
            "hour": datetime.now().hour,
            "modifiers": self.get_all_modifiers(),
        }
