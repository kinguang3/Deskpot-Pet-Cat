"""数据存储模块

负责持久化存储宠物状态、设置、互动记录。
使用 JSON 文件存储。
"""

import json
from pathlib import Path
from typing import Any


class Storage:
    """简单的 JSON 文件存储。"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = str(
                Path(__file__).resolve().parent.parent.parent / "data"
            )
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Any] = {}
        self._loaded = False

    def _get_file_path(self, name: str) -> Path:
        return self._data_dir / f"{name}.json"

    def load(self, name: str = "pet_data") -> dict:
        """加载数据。"""
        path = self._get_file_path(name)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._cache[name] = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache[name] = {}
        else:
            self._cache[name] = {}
        self._loaded = True
        return self._cache[name]

    def save(self, data: dict, name: str = "pet_data"):
        """保存数据。"""
        path = self._get_file_path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self._cache[name] = data

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
            self.save(self._cache[name], name)
