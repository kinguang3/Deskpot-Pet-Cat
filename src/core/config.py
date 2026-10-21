# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""配置管理模块

负责加载、读取、保存配置
配置优先级：用户配置 > 默认配置

路径处理约定：
- default.json 是**只读资源**，随程序分发（安装目录内）
- user.json 是**用户数据**，写在 %APPDATA%/GBC Nina/config/ 下
  （安装目录只读也能正常工作，例如装在 C:\\Program Files）
- 旧版本把 user.json 写在安装目录 config/ 下，首次运行会自动迁移
- 配置文件中的路径可以写成相对路径或绝对路径
- 读取路径类配置时，统一使用 ConfigManager.get_path()
  它会自动把相对路径基于程序资源根目录解析成绝对路径
  这样程序无论从哪个工作目录启动都能正确找到文件
"""

import json
from pathlib import Path

from src.utils.logger import get_logger
from src.utils import json_io, paths

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

        # 资源根目录（只读）：models/ bin/ assets/ config/default.json
        self._base_dir = paths.app_base_dir()
        # 用户配置（可写）：%APPDATA%/GBC Nina/config/user.json
        self._user_config_path = paths.user_config_path()
        self._default_config_path = paths.default_config_path()

        # 旧版本把 user.json 写在安装目录里，先尝试迁移
        paths.migrate_legacy_user_config()

        self._data: dict = {}
        self._load()

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

    def _load_json(self, path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("Config file not found: %s", path.name)
            return {}
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse config file: %s", path.name
            )
            return self._recover_corrupt_json(path)

    def _recover_corrupt_json(self, path: Path) -> dict:
        """配置文件损坏时的恢复策略。

        损坏原因通常是写入过程中进程/系统中断导致文件被截断。实现见
        :func:`src.utils.json_io.recover_with_backup`：优先回退 ``.bak``
        备份，否则把损坏文件隔离为 ``.corrupt`` 再返回空字典。

        关键点：绝不静默返回默认值后就允许 save() 覆盖——那会造成用户
        配置永久丢失（历史上「关闭面板丢设置」的根因之一）。
        """
        return json_io.recover_with_backup(path, label="config")

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

    def save(self) -> bool:
        """原子化保存用户配置到 user.json

        采用「写临时文件 -> fsync -> os.replace」的原子写策略，并把上一份
        完好内容滚动保存为 ``user.json.bak``，供 ``_recover_corrupt_json``
        在文件损坏时回退。实现见 :func:`src.utils.json_io.atomic_write_json`。

        Returns:
            True 表示已成功落盘；False 表示失败（调用方不应再把内存
            状态标记为「已保存」）。
        """
        return json_io.atomic_write_json(
            self._user_config_path,
            self._data,
            label="config",
            create_parent=True,
        )

    def get_all(self) -> dict:
        """返回完整配置副本"""
        return json.loads(json.dumps(self._data))
