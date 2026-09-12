# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""安全动作执行器

执行自定义指令定义的安全动作（打开网页、打开应用）。
"""

import random
import subprocess
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 默认反馈
_DEFAULT_SUCCESS = "好呀～"
_DEFAULT_FAIL = "唔……好像出了点问题……"

# URL 协议白名单
_ALLOWED_URL_SCHEMES = ("http://", "https://")


def execute(action_type: str, target: str, custom_response: str = "") -> tuple[bool, str]:
    """执行安全动作。

    Args:
        action_type: 动作类型 (open_url / open_app)
        target: 动作目标
        custom_response: 用户自定义成功回复

    Returns:
        (是否成功, 反馈文本)
    """
    try:
        if action_type == "open_url":
            return _open_url(target, custom_response)
        elif action_type == "open_app":
            return _open_app(target, custom_response)
        else:
            logger.error("Unknown action type: %s", action_type)
            return False, _DEFAULT_FAIL
    except Exception:
        logger.exception("Action execution failed: %s -> %s", action_type, target)
        return False, _DEFAULT_FAIL


def _open_url(url: str, custom_response: str) -> tuple[bool, str]:
    """打开网页。"""
    if not any(url.startswith(s) for s in _ALLOWED_URL_SCHEMES):
        logger.error("Invalid URL scheme: %s", url)
        return False, "链接格式不对哦～"

    logger.info("[Action] Opening URL: %s", url)
    subprocess.Popen(
        ["cmd", "/c", "start", "", url],
        creationflags=subprocess.DETACHED_PROCESS,
    )
    logger.info("[Action] URL opened successfully")
    response = custom_response or random.choice([
        "好呀，打开啦～",
        "已经帮你打开啦。",
        "网页来啦～",
    ])
    return True, response


def _open_app(path: str, custom_response: str) -> tuple[bool, str]:
    """打开应用。"""
    app_path = Path(path)
    if not app_path.exists():
        logger.error("[Action] App not found: %s", path)
        return False, "唔……找不到这个应用了。"

    logger.info("[Action] Opening app: %s", path)
    subprocess.Popen(
        [str(app_path)],
        creationflags=subprocess.DETACHED_PROCESS,
    )
    logger.info("[Action] App opened successfully")
    response = custom_response or random.choice([
        "好呀，打开啦～",
        "已经帮你打开啦。",
    ])
    return True, response
