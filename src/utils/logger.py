# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""
统一日志模块

提供全局日志配置和获取接口，使用标准 logging 库。
支持控制台和文件输出，文件按时间戳生成，程序退出时自动清理旧文件。
日志格式：时间 | 级别 | 模块名[.类名] | 函数名 | 消息

使用方式:
    from src.utils.logger import setup_logger, get_logger

    setup_logger(debug_mode=True)
    logger = get_logger(__name__)
    logger.info("Application started")
"""

import atexit
import glob
import inspect
import logging
import os
import sys
import time
from logging import Filter, LogRecord, StreamHandler
from pathlib import Path

DEFAULT_LOG_DIR = "./logs"
DEFAULT_LOG_PREFIX = "app"
DEFAULT_MAX_FILES = 3
DEFAULT_DATE_FMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_FMT = (
    "%(asctime)s | %(levelname)-8s | %(name)s%(classname_sep)s%(classname)s | "
    "%(funcName)s | %(message)s"
)

# 全局状态
_initialized = False
_log_dir = None
_log_prefix = None
_max_files = None


class ClassnameFilter(Filter):
    """
    为日志记录添加调用类的名称（classname）。
    同时修正 funcName 和 lineno（避免被包装函数干扰）。
    """

    def filter(self, record: LogRecord) -> bool:
        if hasattr(record, "_caller_filled"):
            return True

        stack = inspect.stack()
        for idx in range(3, len(stack)):
            frame_info = stack[idx]
            frame = frame_info.frame

            # 跳过 logging 内部对象和自身模块的方法
            if "self" in frame.f_locals:
                obj = frame.f_locals["self"]
                if isinstance(
                    obj,
                    (
                        logging.Logger,
                        logging.Handler,
                        logging.Filter,
                        logging.Formatter,
                    ),
                ):
                    continue

            # 跳过本模块中的辅助函数
            if frame_info.function in (
                "debug",
                "info",
                "warning",
                "error",
                "critical",
            ) and frame_info.filename.replace("\\", "/").endswith("logger.py"):
                continue

            # 提取类名
            if "self" in frame.f_locals:
                classname = frame.f_locals["self"].__class__.__name__
            else:
                # 普通函数（无 self）则使用模块名
                classname = frame.f_globals.get("__name__", record.module)

            record.classname = classname
            record.classname_sep = "." if classname else ""
            record.funcName = frame_info.function
            record.lineno = frame_info.lineno
            record._caller_filled = True
            return True

        # 保底
        record.classname = ""
        record.classname_sep = ""
        record._caller_filled = True
        return True


class LevelFilter(Filter):
    """按级别和模式过滤日志记录"""

    def __init__(self, level: int, mode: str = "above"):
        self.level = level
        self.mode = mode  # 'above' | 'below' | 'exact'
        super().__init__()

    def filter(self, record: LogRecord) -> bool:
        if self.mode == "above":
            return record.levelno >= self.level
        elif self.mode == "below":
            return record.levelno <= self.level
        elif self.mode == "exact":
            return record.levelno == self.level
        return True


def _cleanup_old_logs():
    """删除超出数量限制的旧日志文件（按修改时间排序）"""
    if not _log_dir or not _log_prefix:
        return

    pattern = os.path.join(_log_dir, f"{_log_prefix}_*.log")
    files = glob.glob(pattern)
    if len(files) <= _max_files:
        return

    files.sort(key=os.path.getmtime)
    to_delete = files[:-_max_files] if _max_files > 0 else files
    for f in to_delete:
        try:
            os.remove(f)
            # 可选打印清理信息（但此时可能已无控制台）
        except OSError:
            pass


def setup_logger(
    debug_mode: bool = False,
    log_dir: str = DEFAULT_LOG_DIR,
    log_prefix: str = DEFAULT_LOG_PREFIX,
    max_log_files: int = DEFAULT_MAX_FILES,
    console_level: int = None,
    file_level: int = logging.DEBUG,
    filter_level: int = None,
    filter_mode: str = "above",
) -> None:
    """
    初始化日志系统（应在程序入口处调用一次）。

    Args:
        debug_mode: 若为 True，控制台输出 DEBUG 级别；否则 INFO 级别。
        log_dir: 日志文件存放目录。
        log_prefix: 日志文件名前缀。
        max_log_files: 保留的最大日志文件数（超出的在程序退出时删除）。
        console_level: 控制台输出最低级别（若未指定，根据 debug_mode 决定）。
        file_level: 文件输出最低级别（默认 DEBUG）。
        filter_level: 额外过滤级别（若为 None 则不添加过滤器）。
        filter_mode: 过滤模式，可选 'above'（>=）, 'below'（<=）, 'exact'（==）。
    """
    global _initialized, _log_dir, _log_prefix, _max_files

    if _initialized:
        return
    _initialized = True

    _log_dir = log_dir.strip()
    _log_prefix = log_prefix.strip()
    _max_files = max_log_files

    # 创建日志目录
    try:
        os.makedirs(_log_dir, exist_ok=True)
    except OSError as e:
        print(
            f"Failed to create log directory {_log_dir}: {e}", file=sys.stderr
        )
        return

    # 生成带时间戳的日志文件名
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    log_filename = f"{_log_prefix}_{timestamp}.log"
    log_path = os.path.join(_log_dir, log_filename)

    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(DEFAULT_LOG_FMT, DEFAULT_DATE_FMT)

    # 文件 Handler
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    # 添加类名过滤器
    file_handler.addFilter(ClassnameFilter())
    # 添加级别过滤器
    if filter_level is not None:
        file_handler.addFilter(LevelFilter(filter_level, filter_mode))
    root_logger.addHandler(file_handler)

    # 控制台 Handler
    if console_level is None:
        console_level = logging.DEBUG if debug_mode else logging.INFO
    console_handler = StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ClassnameFilter())
    if filter_level is not None:
        console_handler.addFilter(LevelFilter(filter_level, filter_mode))
    root_logger.addHandler(console_handler)

    # 写入启动标记
    root_logger.info(
        "Logging started. File: %s",
        log_path,
        extra={"classname": "LoggerInit"},
    )

    # 注册程序退出时清理旧日志
    atexit.register(_cleanup_old_logs)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定模块的 logger。

    Args:
        name: 模块名称，通常传 __name__。

    Returns:
        logging.Logger 实例。
    """
    return logging.getLogger(name)
