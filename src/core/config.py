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
import os
import shutil
from pathlib import Path

from src.utils.logger import get_logger
from src.utils import paths

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
        self._config_dir = paths.user_config_path().parent
        self._user_config_path = paths.user_config_path()
        self._default_config_path = paths.default_config_path()

        # 旧版本把 user.json 写在安装目录里，先尝试迁移
        paths.migrate_legacy_user_config()

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
        """配置文件损坏时的恢复策略

        损坏原因通常是写入过程中进程/系统中断导致文件被截断。处理顺序：
        1. 尝试加载同目录的备份 ``<name>.bak``（每次成功保存都会滚动保留
           上一份完好的内容）；
        2. 备份可用则返回备份内容，并把损坏文件隔离为 ``<name>.corrupt``
           防止后续 save() 用默认值静默覆盖用户的真实配置；
        3. 备份也不可用时同样隔离损坏文件，返回空字典。

        关键点：绝不静默返回默认值后就允许 save() 覆盖——那会造成用户
        配置永久丢失（历史上「关闭面板丢设置」的根因之一）。
        """
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            try:
                with open(backup, "r", encoding="utf-8") as f:
                    recovered = json.load(f)
                logger.warning(
                    "Recovered config from backup: %s", backup.name
                )
                self._quarantine(path)
                return recovered
            except (OSError, json.JSONDecodeError):
                logger.warning("Config backup also unusable: %s", backup.name)

        self._quarantine(path)
        logger.error(
            "Config file corrupted and no usable backup; using defaults. "
            "Corrupt file kept at %s",
            path.with_suffix(path.suffix + ".corrupt").name,
        )
        return {}

    @staticmethod
    def _quarantine(path: Path) -> None:
        """把损坏文件改名隔离，避免被后续写入覆盖"""
        try:
            target = path.with_suffix(path.suffix + ".corrupt")
            path.replace(target)
        except OSError:
            logger.warning("Failed to quarantine corrupt config: %s", path)

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

        采用「写临时文件 -> fsync -> os.replace」的原子写策略：
        os.replace 在同一文件系统内是原子操作，因此进程崩溃、磁盘写满
        或断电时，user.json 要么保持旧内容，要么变成完整的新内容，
        不会出现被截断的非法 JSON。

        同时把上一份完好内容滚动保存为 ``user.json.bak``，供
        ``_recover_corrupt_json`` 在文件损坏时回退。

        Returns:
            True 表示已成功落盘；False 表示失败（调用方不应再把内存
            状态标记为「已保存」）。
        """
        tmp_path = self._user_config_path.with_suffix(".json.tmp")
        backup = self._user_config_path.with_suffix(".json.bak")
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)

            # 先序列化到内存，提前暴露不可序列化类型，避免写坏文件
            payload = json.dumps(self._data, indent=4, ensure_ascii=False)

            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

            # 落盘成功后，滚动保留上一份完好内容
            if self._user_config_path.exists():
                try:
                    shutil.copy2(self._user_config_path, backup)
                except OSError:
                    logger.warning("Failed to refresh config backup")

            os.replace(tmp_path, self._user_config_path)
            logger.debug("Settings saved atomically")
            return True
        except (OSError, TypeError, ValueError):
            # TypeError/ValueError: 配置里混入不可 JSON 序列化的值
            logger.exception("Failed to save settings")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False

    def get_all(self) -> dict:
        """返回完整配置副本"""
        return json.loads(json.dumps(self._data))
