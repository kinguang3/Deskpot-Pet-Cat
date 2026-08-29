# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""调试、日志输出模块核心

启动后自动导出日志信息。
调试信息依照如下格式：
    [classname]<funcName>(levelname): message
"""

import logging
import os
import time
import glob
import atexit
import inspect
import sys

from logging import Filter, LogRecord, StreamHandler


class LevelFilter(Filter):
    """过滤器：按级别过滤"""

    def __init__(self, level: int, mode: str = 'above'):
        self.level = level
        self.mode = mode
        super().__init__()

    def filter(self, record: LogRecord) -> bool:
        if self.mode == 'above':
            return record.levelno >= self.level
        elif self.mode == 'below':
            return record.levelno <= self.level
        elif self.mode == 'exact':
            return record.levelno == self.level
        return True


class ClassnameFilter(Filter):
    """添加类名

    为每条日志记录自动添加调用类的名称到 record.classname
    """

    def filter(self, record: LogRecord) -> bool:
        if hasattr(record, '_caller_filled'):
            return True

        stack = inspect.stack()

        for idx in range(3, len(stack)):
            frame_info = stack[idx]
            frame = frame_info.frame

            # 跳过 CustomLogger 自身的方法
            if 'self' in frame.f_locals:
                obj = frame.f_locals['self']
                if isinstance(obj, CustomLogger):
                    continue
                # 也跳过 logging 内部对象
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

            # 额外保护：如果函数名是 info/warning 等且位于 log_core.py，跳过
            if frame_info.function in (
                'debug',
                'info',
                'warning',
                'error',
                'critical',
            ) and frame_info.filename.replace('\\', '/').endswith(
                'log_core.py'
            ):
                continue

            if 'self' in frame.f_locals:
                record.classname = frame.f_locals['self'].__class__.__name__
            else:
                # 如果是普通函数（无 self），用模块名
                record.classname = frame.f_globals.get(
                    '__name__', record.module
                )

            # 修正函数名和行号
            record.funcName = frame_info.function
            record.lineno = frame_info.lineno

            record._caller_filled = True
            return True

        # 保底逻辑
        record._caller_filled = True
        return True


class CustomLogger:
    """通用日志类"""

    """
    :param log_dir: 日志存放目录
    :param log_prefix: 日志文件名前缀
    :param max_log_files: 最多保留的日志文件数（超出的在 stop() 时删除）
    :param level: 全局日志级别（logger 级别）
    :param fmt: 日志格式，若为 None 则使用 "[%(classname)s]<%(funcName)s>(%(levelname)s): %(message)s"
    :param datefmt: 时间格式
    :param filter_level: 过滤级别（若未指定，默认与 level 相同）
    :param filter_mode: 过滤模式 ('above'|'below'|'exact')
    """

    def __init__(
        self,
        log_dir: str,
        log_prefix: str = 'app',
        max_log_files: int = 3,
        level: int = logging.INFO,
        # 若未提供，使用默认带类名的格式
        fmt: str = None,
        datefmt: str = '%Y-%m-%d %H:%M:%S',
        filter_level: int = None,
        filter_mode: str = 'above',
        console_output: bool = True,
    ):

        self.log_dir = log_dir.strip().replace('\n', '').replace('\r', '')
        self.log_prefix = (
            log_prefix.strip().replace('\n', '').replace('\r', '')
        )
        self.max_log_files = max_log_files
        self.level = level
        self.datefmt = datefmt
        self.filter_level = filter_level if filter_level is not None else level
        self.filter_mode = filter_mode
        self.console_output = console_output
        self.console_handler = None

        # 默认格式
        if fmt is None:
            self.fmt = (
                "[%(classname)s]<%(funcName)s>(%(levelname)s): %(message)s"
            )
        else:
            self.fmt = fmt

        self.logger = None
        self.handler = None
        self.level_filter = None
        self.class_filter = None
        self.current_log_file = None

        # 注册程序退出时自动清理
        atexit.register(self.stop)

    def start(self):
        """启动日志记录"""
        if self.logger is not None:
            return

        os.makedirs(self.log_dir, exist_ok=True)

        # 按时间生成唯一的日志文件名
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        log_filename = f"{self.log_prefix}_{timestamp}.log"
        log_path = os.path.join(self.log_dir, log_filename)
        self.current_log_file = log_path
        log_path = os.path.join(self.log_dir, log_filename)
        log_path = log_path.replace('\\', '/')

        # 创建 logger
        logger_name = f'CustomLogger_{id(self)}'
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self.level)

        # 创建 FileHandler
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(self.fmt, self.datefmt)
        file_handler.setFormatter(formatter)

        # 添加过滤器（注意顺序：先类名过滤器，再级别过滤器）
        self.class_filter = ClassnameFilter()
        file_handler.addFilter(self.class_filter)
        self.level_filter = LevelFilter(self.filter_level, self.filter_mode)
        file_handler.addFilter(self.level_filter)

        # 将 handler 加入 logger
        self.logger.addHandler(file_handler)
        self.handler = file_handler

        # 控制台 Handler
        if self.console_output:
            console_handler = StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            console_handler.addFilter(self.class_filter)
            console_handler.addFilter(self.level_filter)
            self.logger.addHandler(console_handler)
            self.console_handler = console_handler

        # 写入启动标记
        self.logger.info(
            "Logging started. File: %s",
            log_path,
            extra={'classname': 'CustomLogger'},
        )

    def stop(self):
        """停止日志记录并清理多余日志文件"""
        if self.logger is None:
            return

        self.logger.info("Logging stopped.")

        # 移除 handler 并关闭文件
        self.logger.removeHandler(self.handler)
        self.handler.close()

        # 如果启用控制台，移除控制台 Handler
        if self.console_handler:
            self.logger.removeHandler(self.console_handler)
            self.console_handler.close()
            self.console_handler = None

        # 清理多余日志文件
        self._cleanup_old_logs()

        # 重置状态
        self.logger = None
        self.handler = None
        self.level_filter = None
        self.class_filter = None

    def set_log_level(self, level: int):
        """修改 logger 的全局级别"""
        if self.logger:
            self.logger.setLevel(level)
            self.level = level

    def set_filter(self, level: int, mode: str = 'above'):
        """修改过滤器的级别和模式（实时生效，只影响后续日志）"""
        if self.level_filter:
            self.level_filter.level = level
            self.level_filter.mode = mode

    def _cleanup_old_logs(self):
        """清理旧日志文件"""
        pattern = os.path.join(self.log_dir, f"{self.log_prefix}_*.log")
        files = glob.glob(pattern)
        if len(files) <= self.max_log_files:
            return

        files.sort(key=os.path.getmtime)
        to_delete = (
            files[: -self.max_log_files] if self.max_log_files > 0 else files
        )
        for f in to_delete:
            try:
                os.remove(f)
                print(f"[Cleanup] Removed old log: {f}")
            except OSError as e:
                print(f"[Cleanup] Failed to remove {f}: {e}")

    def debug(self, msg, *args, **kwargs):
        if self.logger:
            self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        if self.logger:
            self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        if self.logger:
            self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        if self.logger:
            self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        if self.logger:
            self.logger.critical(msg, *args, **kwargs)

    def get_logger(self):
        return self.logger
