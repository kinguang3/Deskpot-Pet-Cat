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
    OPEN_BROWSER = "open_browser"
    UNKNOWN = "unknown"


# 每个意图的匹配关键词
_TIME_KEYWORDS = [
    r"几\s*点",
    r"什么\s*时间",
    r"现在\s*时间",
    r"几\s*点\s*了",
    r"现在\s*几\s*点",
]

_BROWSER_KEYWORDS = [
    r"打\s*开\s*浏览器",
    r"开\s*浏览器",
    r"打\s*开\s*网页",
    r"开\s*网页",
    r"打\s*开\s*一?\s*下\s*浏览器",
    r"打\s*开\s*一?\s*下\s*网页",
]


class CommandParser:
    """语音命令意图解析器。"""

    def __init__(self):
        self._time_patterns = [re.compile(kw) for kw in _TIME_KEYWORDS]
        self._browser_patterns = [re.compile(kw) for kw in _BROWSER_KEYWORDS]

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

        # 检查打开浏览器
        for pattern in self._browser_patterns:
            if pattern.search(text):
                logger.info("Intent matched: open_browser (text=%s)", text)
                return Intent.OPEN_BROWSER, {"text": text}

        logger.debug("Intent unknown: %s", text)
        return Intent.UNKNOWN, {"text": text}
