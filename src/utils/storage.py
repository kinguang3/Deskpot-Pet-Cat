"""数据存储模块

负责持久化存储宠物状态、设置、互动记录。
使用 JSON 文件存储。

数据目录位于用户数据目录（%APPDATA%/GBC Nina/data），
不写在程序安装目录里，因此装到 C:\\Program Files 也能正常读写。
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger
from src.utils import paths

logger = get_logger(__name__)


class Storage:
    """简单的 JSON 文件存储。"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = str(paths.data_path())

        self._data_dir = Path(data_dir)
        self._available = True

        # 建目录失败不能让程序起不来：降级为「不持久化」，
        # 桌宠仍可正常运行，只是这次不保存记忆。
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._available = False
            logger.error(
                "Data dir %s unavailable; running without persistence",
                self._data_dir,
                exc_info=True,
            )

        self._cache: dict[str, Any] = {}
        self._loaded = False
        logger.debug(
            "Storage initialized (dir: %s, available: %s)",
            self._data_dir,
            self._available,
        )

    @property
    def available(self) -> bool:
        """数据目录是否可用（False 表示本次运行不会持久化）。"""
        return self._available

    def _get_file_path(self, name: str) -> Path:
        return self._data_dir / f"{name}.json"

    def load(self, name: str = "pet_data") -> dict:
        """加载数据。

        损坏的 JSON 不会静默清空：先尝试回退到 ``.bak`` 备份，再把损坏
        文件隔离为 ``.corrupt``，避免用户数据被默认值覆盖。
        """
        path = self._get_file_path(name)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._cache[name] = json.load(f)
                logger.debug("Data loaded: %s", name)
            except json.JSONDecodeError:
                logger.error("Failed to parse data file: %s", path.name)
                self._cache[name] = self._recover_corrupt(path)
            except OSError:
                logger.error("Failed to read data file: %s", path.name)
                self._cache[name] = {}
        else:
            self._cache[name] = {}
            logger.debug("Data file not found, using empty: %s", name)
        self._loaded = True
        return self._cache[name]

    def _recover_corrupt(self, path: Path) -> dict:
        """数据文件损坏时的恢复：优先用 .bak，再隔离损坏文件"""
        backup = path.with_suffix(".json.bak")
        if backup.exists():
            try:
                with open(backup, "r", encoding="utf-8") as f:
                    recovered = json.load(f)
                logger.warning(
                    "Recovered data from backup: %s", backup.name
                )
                self._quarantine(path)
                return recovered
            except (OSError, json.JSONDecodeError):
                logger.warning("Data backup also unusable: %s", backup.name)

        self._quarantine(path)
        logger.error(
            "Data file corrupted and no usable backup; starting empty. "
            "Corrupt file kept at %s",
            path.with_suffix(".json.corrupt").name,
        )
        return {}

    @staticmethod
    def _quarantine(path: Path) -> None:
        """把损坏文件改名隔离，避免被后续写入覆盖"""
        try:
            path.replace(path.with_suffix(".json.corrupt"))
        except OSError:
            logger.warning("Failed to quarantine corrupt data file: %s", path)

    def save(self, data: dict, name: str = "pet_data") -> bool:
        """原子化保存数据。

        先序列化到内存，再写临时文件并 fsync，最后 os.replace 原子替换。
        这样进程崩溃/断电时目标文件要么是旧内容、要么是完整新内容，
        不会出现被截断的非法 JSON（否则下次 load 会静默清空数据）。

        Returns:
            True 成功落盘；False 失败（调用方可据此重试）。
        """
        path = self._get_file_path(name)
        tmp_path = path.with_suffix(".json.tmp")
        backup_path = path.with_suffix(".json.bak")
        try:
            # 提前序列化，暴露不可 JSON 序列化的值
            payload = json.dumps(data, indent=4, ensure_ascii=False)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            # 覆盖前滚动保留上一份完好内容，供 load() 损坏时回退
            if path.exists():
                shutil.copy2(path, backup_path)
            os.replace(tmp_path, path)
            self._cache[name] = data
            logger.debug("Data saved: %s", name)
            return True
        except (OSError, TypeError, ValueError):
            logger.exception("Failed to save data: %s", name)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False

    def get(self, key: str, default=None, name: str = "pet_data") -> Any:
        """获取单个值。"""
        if not self._loaded:
            self.load(name)
        data = self._cache.get(name, {})
        return data.get(key, default)

    def set(self, key: str, value: Any, name: str = "pet_data"):
        """设置单个值。"""
        if not self._loaded:
            self.load(name)
        if name not in self._cache:
            self._cache[name] = {}
        self._cache[name][key] = value

    def save_all(self, name: str = "pet_data"):
        """保存所有缓存数据。"""
        if name in self._cache:
            return self.save(self._cache[name], name)
        return False
