# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""配置管理模块

负责加载、读取、保存配置
配置优先级：用户配置 > 默认配置

路径处理约定：
- 配置文件中的路径可以写成相对路径（相对于项目根目录）或绝对路径
- 读取路径类配置时，统一使用 ConfigManager.get_path()
  它会自动把相对路径基于项目根目录解析成绝对路径
  这样程序无论从哪个工作目录启动都能正确找到文件
"""

import json
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """管理应用配置的单例式管理器"""

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

    # 基础属性

    @property
    def base_dir(self) -> Path:
        """项目根目录的绝对路径"""
        return self._base_dir

    @property
    def config_dir(self) -> Path:
        """配置文件所在目录的绝对路径"""
        return self._config_dir

    # 加载与保存

    def _load(self):
        """加载配置，用户配置覆盖默认配置"""
        self._data = self._load_json(self._default_config_path)
        if self._user_config_path.exists():
            user_cfg = self._load_json(self._user_config_path)
            self._deep_merge(self._data, user_cfg)
            logger.info("User config loaded and merged")
        else:
            logger.debug("No user config found, using defaults")

    def reload(self):
        """重新从磁盘加载配置，丢弃当前内存中的数据"""
        self._load()
        logger.info("Config reloaded")

    def _load_json(self, path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("Config file not found: %s", path.name)
            return {}
        except json.JSONDecodeError:
            logger.error("Failed to parse config file: %s", path.name)
            return {}

    def _deep_merge(self, base: dict, override: dict):
        """将 override 的值深度合并到 base 中"""
        for key, value in override.items():
            if (
                key in base
                and isinstance(base[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    # 读取

    def get(self, key_path: str, default=None):
        """通过点分路径获取配置值

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

    def get_path(self, key_path: str, default=None):
        """读取路径类配置，并解析为绝对路径

        规则：
        - 空值或 None 返回 None
        - 以 ~ 开头会展开为用户主目录
        - 绝对路径原样返回（做一次 resolve 规范化）
        - 相对路径基于项目根目录解析

        例如:
            config.get_path("voice.sensevoice.exe_path")
        """
        value = self.get(key_path, default)
        if value is None or value == "":
            return None

        p = Path(str(value)).expanduser()
        if not p.is_absolute():
            p = self._base_dir / p

        try:
            return p.resolve()
        except OSError:
            # 某些平台在路径不存在时 resolve 也可能抛异常
            # 退回到绝对路径拼接结果
            logger.warning("Failed to resolve path: %s", p)
            return p.absolute()

    # 写入

    def set(self, key_path: str, value):
        """通过点分路径设置配置值"""
        keys = key_path.split(".")
        node = self._data
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value

    def save(self):
        """保存用户配置到 user.json"""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._user_config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
            logger.debug("Settings saved")
        except OSError:
            logger.exception("Failed to save settings")

    def get_all(self) -> dict:
        """返回完整配置副本"""
        return json.loads(json.dumps(self._data))
