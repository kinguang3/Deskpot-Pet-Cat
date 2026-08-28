# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""配置管理模块

负责加载、读取、保存配置。
配置优先级：用户配置 > 默认配置。
"""

import json
import os
from pathlib import Path


class ConfigManager:
    """管理应用配置的单例式管理器。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._base_dir = Path(__file__).resolve().parent.parent.parent
        self._config_dir = self._base_dir / "config"
        self._user_config_path = self._config_dir / "user.json"
        self._default_config_path = self._config_dir / "default.json"

        self._data: dict = {}
        self._load()

    def _load(self):
        """加载配置，用户配置覆盖默认配置。"""
        self._data = self._load_json(self._default_config_path)
        if self._user_config_path.exists():
            user_cfg = self._load_json(self._user_config_path)
            self._deep_merge(self._data, user_cfg)

    def _load_json(self, path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _deep_merge(self, base: dict, override: dict):
        """将 override 的值深度合并到 base 中。"""
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key_path: str, default=None):
        """通过点分路径获取配置值。

        例如: config.get("window.opacity")
        """
        keys = key_path.split(".")
        node = self._data
        for key in keys:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                return default
        return node

    def set(self, key_path: str, value):
        """通过点分路径设置配置值。"""
        keys = key_path.split(".")
        node = self._data
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value

    def save(self):
        """保存用户配置到 user.json。"""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._user_config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    def get_all(self) -> dict:
        """返回完整配置副本。"""
        return json.loads(json.dumps(self._data))
