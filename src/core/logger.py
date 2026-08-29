# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

import logging

from .log_core import CustomLogger

"""全局日志单例"""

# 全局单例
log = CustomLogger(
    log_dir='./logs',
    log_prefix='log',
    max_log_files=3,
    level=logging.DEBUG,
    filter_level=logging.INFO,
    filter_mode='above',
    fmt=None,
    datefmt='%Y-%m-%d %H:%M:%S',
)
log.start()
