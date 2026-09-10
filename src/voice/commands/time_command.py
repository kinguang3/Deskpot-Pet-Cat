# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""时间查询命令处理器

获取系统本地时间，返回中文格式化文本。
"""

from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 时段名称
_PERIODS = [
    (0, 6, "凌晨"),
    (6, 12, "上午"),
    (12, 13, "中午"),
    (13, 18, "下午"),
    (18, 24, "晚上"),
]


def _get_period(hour: int) -> str:
    """根据小时数返回时段名称。"""
    for start, end, name in _PERIODS:
        if start <= hour < end:
            return name
    return "凌晨"


def get_time_response() -> str:
    """获取当前时间的中文格式化回答。

    Returns:
        如「现在是下午 3 点 23 分。」或「现在是下午 3 点。」
    """
    try:
        now = datetime.now()
        period = _get_period(now.hour)
        hour_12 = now.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        minute = now.minute

        if minute == 0:
            return f"现在是{period}{hour_12}点。"
        else:
            # 分钟补零：5分→05分
            return f"现在是{period}{hour_12}点{minute:02d}分。"

    except Exception:
        logger.exception("Failed to get system time")
        return "我好像没看清时间……"
