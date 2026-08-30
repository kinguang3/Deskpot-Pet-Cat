# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""日志模块

提供统一的日志配置和获取接口。
使用 Python 标准库 logging，支持控制台和文件输出。
"""

import logging
import logging.handlers
import sys
from pathlib import Path


# 日志格式
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志目录
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "nina.log"

# 文件日志配置
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3

# 全局标记：是否已初始化
_initialized = False


def setup_logger(debug_mode: bool = False) -> None:
    """初始化日志系统。

    应在程序入口 (main.py) 中调用一次。

    Args:
        debug_mode: True=DEBUG级别, False=INFO级别
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除已有的 handler（避免重复）
    root_logger.handlers.clear()

    level = logging.DEBUG if debug_mode else logging.INFO

    # ─── Console Handler ───
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # ─── File Handler (Rotating) ───
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            str(LOG_FILE),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # 文件始终记录 DEBUG
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root_logger.addHandler(file_handler)
    except OSError as e:
        root_logger.warning("Failed to create log file: %s", e)


def get_logger(name: str) -> logging.Logger:
    """获取指定模块的 logger。

    使用方式::

        logger = get_logger(__name__)
        logger.info("Application started")

    Args:
        name: 模块名称，通常传 __name__

    Returns:
        logging.Logger 实例
    """
    return logging.getLogger(name)
