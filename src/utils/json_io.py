# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""JSON 文件持久化的公共实现。

用户配置（``ConfigManager``）与互动数据（``Storage``）原本各有一份几乎
相同的「原子写 + 备份回退 + 损坏隔离」逻辑，这里合并为一处，避免两套
实现日后行为漂移。

约定备份/隔离文件与目标同目录、同主名：
``foo.json`` -> ``foo.json.bak`` / ``foo.json.corrupt`` / ``foo.json.tmp``。
"""

import json
import os
import shutil
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


def atomic_write_json(
    path,
    data: dict,
    *,
    label: str,
    create_parent: bool = False,
    strict_backup: bool = False,
) -> bool:
    """原子写入 JSON。

    先序列化到内存，再写临时文件并 fsync，最后 ``os.replace`` 原子替换。
    这样进程崩溃/断电时目标文件要么是旧内容、要么是完整新内容，不会出现
    被截断的非法 JSON（否则下次读取会静默清空数据）。

    Args:
        path: 目标文件路径。
        data: 待写入的字典。
        label: 日志中标识用途（如 ``"config"`` / ``"data"``）。
        create_parent: 写入前是否创建父目录。
        strict_backup: 备份滚动失败时是否视为保存失败。``ConfigManager``
            历史上容忍备份失败（仅告警），``Storage`` 则视为失败；保留
            两种语义以免改变既有行为。

    Returns:
        True 成功落盘；False 失败（调用方可据此重试）。
    """
    path = Path(path)
    tmp_path = path.with_suffix(".json.tmp")
    backup_path = path.with_suffix(".json.bak")
    try:
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True)

        # 提前序列化，暴露不可 JSON 序列化的值
        payload = json.dumps(data, indent=4, ensure_ascii=False)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        # 覆盖前滚动保留上一份完好内容，供读取损坏时回退
        if path.exists():
            try:
                shutil.copy2(path, backup_path)
            except OSError:
                if strict_backup:
                    raise
                logger.warning(
                    "Failed to refresh %s backup: %s", label, backup_path.name
                )

        os.replace(tmp_path, path)
        logger.debug("%s saved atomically: %s", label, path.name)
        return True
    except (OSError, TypeError, ValueError):
        logger.exception("Failed to save %s: %s", label, path.name)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        return False


def recover_with_backup(path, *, label: str) -> dict:
    """读取损坏 JSON 时的恢复：优先用 ``.bak``，否则隔离损坏文件。

    绝不静默返回默认值后就允许后续写入覆盖——那会造成用户数据永久丢失。
    返回空字典表示文件和备份都不可用，调用方应据此降级。
    """
    path = Path(path)
    backup = path.with_suffix(".json.bak")
    if backup.exists():
        try:
            with open(backup, "r", encoding="utf-8") as f:
                recovered = json.load(f)
            logger.warning("Recovered %s from backup: %s", label, backup.name)
            quarantine(path, label=label)
            return recovered
        except (OSError, json.JSONDecodeError):
            logger.warning("%s backup also unusable: %s", label, backup.name)

    quarantine(path, label=label)
    logger.error(
        "%s corrupted and no usable backup; using empty. Corrupt file kept at %s",
        label,
        path.with_suffix(".json.corrupt").name,
    )
    return {}


def quarantine(path, *, label: str) -> None:
    """把损坏文件改名隔离，避免被后续写入覆盖。"""
    path = Path(path)
    try:
        path.replace(path.with_suffix(".json.corrupt"))
    except OSError:
        logger.warning("Failed to quarantine corrupt %s: %s", label, path)
