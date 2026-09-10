# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音命令解析器

识别用户语音命令的意图（Intent），不做业务处理。
"""

import re
from enum import Enum
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Intent(Enum):
    """命令意图枚举。"""
    TIME_QUERY = "time_query"
    UNKNOWN = "unknown"


# 每个意图的匹配关键词
_TIME_KEYWORDS = [
    r"几点",
    r"什么时间",
    r"现在时间",
    r"几点了",
    r"现在几点",
]


class CommandParser:
    """语音命令意图解析器。"""

    def __init__(self):
        self._time_patterns = [re.compile(kw) for kw in _TIME_KEYWORDS]

    def parse(self, text: str) -> tuple[Intent, dict]:
        """解析文本，返回 (意图, 数据)。

        Args:
            text: ASR 识别出的文本（已小写化）

        Returns:
            (Intent, 数据字典)
        """
        text = text.strip().lower()

        if not text:
            return Intent.UNKNOWN, {}

        # 检查时间查询
        for pattern in self._time_patterns:
            if pattern.search(text):
                logger.info("Intent matched: time_query (text=%s)", text)
                return Intent.TIME_QUERY, {"text": text}

        logger.debug("Intent unknown: %s", text)
        return Intent.UNKNOWN, {"text": text}
