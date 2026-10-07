# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""路径解析模块

区分两类路径，这是绿色免安装包能安全运行的关键：

- **程序资源目录（只读）**：exe 所在目录下的 `_internal/`（PyInstaller
  onedir）或源码根目录。`assets/` `bin/` `models/` `config/default.json`
  都在这里，属于程序文件，**不应该被写入**。

- **用户数据目录（可写）**：`%APPDATA%/GBC Nina/`。存 `user.json`、
  `data/`、`logs/`、`temp/`。

历史问题：所有写入都落在安装目录内（config/、data/、temp/、logs/），
一旦用户把程序解压到 `C:\\Program Files\\` 就会连环失败：
`Storage.__init__` 的 `mkdir` 没有 try/except 直接崩在启动；
`config.save()` 返回 False 但只写日志，用户看到「点了保存没反应」。

本模块把可写数据统一挪到 %APPDATA%，安装目录变成纯只读，
并对旧版本遗留在安装目录下的配置做一次性迁移。
"""

import os
import shutil
import sys
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

#: 用户数据目录名（%APPDATA% 下的子目录名）
APP_DIR_NAME = "GBC Nina"

#: 便携模式开关。存在该文件时，用户数据写在程序目录旁（绿色模式），
#: 便于 U 盘携带。放在 exe 同级。
PORTABLE_MARKER = "portable.txt"


def app_base_dir() -> Path:
    """程序资源根目录（只读）。

    源码运行 = 仓库根目录；PyInstaller onedir = exe 同级的 `_internal/`。
    两种情况都靠 __file__ 向上定位，不依赖 sys._MEIPASS。
    """
    return Path(__file__).resolve().parent.parent.parent


def portable_mode() -> bool:
    """是否启用便携模式（数据写在程序目录旁）。

    标记文件放在 exe 同级（安装器的便携模式选项也写在那里）。注意
    ``app_base_dir()`` 在冻结包里指向 ``_internal/``，而 portable.txt 在
    exe 旁边，二者不同目录 —— 必须都要检查。
    """
    for base in _portable_candidates():
        if (base / PORTABLE_MARKER).exists():
            return True
    return False


def _portable_candidates() -> list[Path]:
    """便携标记可能存在的目录：exe 同级优先，其次 _internal/（源码根）。"""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        return [exe_dir, app_base_dir()]
    return [app_base_dir()]


def portable_data_base() -> Path:
    """便携模式下用户数据落在哪个目录（与 portable.txt 放在同一层）。"""
    for base in _portable_candidates():
        if (base / PORTABLE_MARKER).exists():
            return base
    return app_base_dir()


def user_data_dir() -> Path:
    """用户数据根目录（可写）。

    优先级：
    1. 环境变量 ``GBC_NINA_HOME``（显式覆盖，最高优先级）
    2. 程序目录旁存在 portable.txt → 程序目录/data_portable（绿色模式）
    3. ``%APPDATA%/GBC Nina``（Windows 标准位置）
    4. 兜底 ``~/.gbc_nina``

    目录创建失败时返回路径而不抛异常（调用方负责降级处理）。
    """
    override = os.environ.get("GBC_NINA_HOME")
    if override:
        base = Path(override).expanduser()
    elif portable_mode():
        base = portable_data_base() / "data_portable"
    else:
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata) / APP_DIR_NAME
        else:
            base = Path.home() / ".gbc_nina"

    ensure_dir(base)
    return base


def ensure_dir(path) -> bool:
    """确保目录存在。返回是否成功（不抛异常，接受 str 或 Path）。"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        logger.warning("Failed to create directory: %s", path, exc_info=True)
        return False


def is_writable(path) -> bool:
    """检查目录（或其最近的已存在祖先）是否可写。"""
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return os.access(str(probe), os.W_OK)


def writable_dir(preferred) -> Path:
    """返回可写的目录（接受 str 或 Path）。

    ``preferred`` 不可写时回退到用户数据目录下的同名子目录。
    用于 temp 等运行时中间产物。
    """
    preferred = Path(preferred)
    if is_writable(preferred.parent if preferred.suffix else preferred):
        return preferred
    fallback = user_data_dir() / preferred.name
    logger.info(
        "Directory %s not writable, falling back to %s", preferred, fallback
    )
    ensure_dir(fallback)
    return fallback


# ─── 具体路径 ───


def user_config_path() -> Path:
    """用户配置文件 %APPDATA%/GBC Nina/config/user.json"""
    return user_data_dir() / "config" / "user.json"


def default_config_path() -> Path:
    """默认配置文件（只读资源）：优先程序目录，找不到回退用户目录。"""
    packaged = app_base_dir() / "config" / "default.json"
    if packaged.exists():
        return packaged
    return user_data_dir() / "config" / "default.json"


def legacy_user_config_path() -> Path:
    """旧版本把 user.json 写在安装目录 config/ 下。"""
    return app_base_dir() / "config" / "user.json"


def data_path() -> Path:
    """互动记忆等持久化数据目录。"""
    return user_data_dir() / "data"


def log_dir() -> Path:
    """日志目录。

    修掉原来的 ``DEFAULT_LOG_DIR = './logs'``：相对路径基于当前工作目录，
    双击 exe 时 CWD 不一定是 exe 目录，日志会散落到别处。
    """
    return user_data_dir() / "logs"


def temp_path() -> Path:
    """语音推理的临时 WAV 目录。"""
    return user_data_dir() / "temp"


def legacy_data_dir() -> Path:
    """旧版本把 data/（互动记忆等）写在安装目录下。"""
    return app_base_dir() / "data"


def migrate_legacy_user_data() -> bool:
    """把旧版写在安装目录 data/ 下的用户文件迁移到用户数据目录。

    只复制目标不存在的文件（目标优先，绝不覆盖）。
    幂等，可安全重复调用。返回是否迁移了任何文件。
    """
    legacy = legacy_data_dir()
    if not legacy.is_dir():
        return False

    target = data_path()
    moved = 0
    try:
        for src in sorted(legacy.iterdir()):
            if not src.is_file():
                continue
            dst = target / src.name
            if dst.exists():
                continue
            ensure_dir(target)
            shutil.copy2(src, dst)
            moved += 1
    except OSError:
        logger.warning("Failed to migrate legacy user data", exc_info=True)
        return False

    if moved:
        logger.info(
            "Migrated %d legacy data file(s) from %s to %s",
            moved,
            legacy,
            target,
        )
    return moved > 0


def migrate_legacy_user_config() -> bool:
    """把旧版写在安装目录的 user.json 迁移到用户数据目录。

    仅在目标不存在时迁移（目标优先，绝不覆盖用户已有配置）。
    迁移后保留原文件不动，用户可自行删除。
    """
    legacy = legacy_user_config_path()
    if not legacy.exists():
        return False

    target = user_config_path()
    if target.exists():
        return False

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
        logger.info(
            "Migrated legacy config from %s to %s", legacy, target
        )
        return True
    except OSError:
        logger.warning("Failed to migrate legacy config", exc_info=True)
        return False
