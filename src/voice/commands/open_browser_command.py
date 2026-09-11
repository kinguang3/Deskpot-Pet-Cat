# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""打开浏览器命令处理器

使用系统默认方式打开浏览器。
"""

import os
import random
import subprocess

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 成功反馈（随机选择）
_SUCCESS_RESPONSES = [
    "好呀，浏览器打开啦～",
    "收到，马上打开～",
    "已经帮你打开啦。",
    "浏览器来啦～",
]

# 失败反馈
_FAIL_RESPONSE = "唔……浏览器好像没有打开。"


def open_browser() -> tuple[bool, str]:
    """打开系统默认浏览器。

    Returns:
        (是否成功, 反馈文本)
    """
    try:
        logger.info("[System] Opening default browser")
        # Windows: 通过 start 命令打开默认浏览器
        subprocess.Popen(
            ["cmd", "/c", "start", "", "https://www.bing.com"],
            creationflags=subprocess.DETACHED_PROCESS,
        )
        logger.info("[System] Browser opened successfully")
        return True, random.choice(_SUCCESS_RESPONSES)
    except Exception:
        logger.exception("[System] Failed to open browser")
        return False, _FAIL_RESPONSE
