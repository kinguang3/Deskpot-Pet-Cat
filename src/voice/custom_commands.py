# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""自定义语音指令管理器

管理用户自定义的语音指令（触发词 → 动作）。
数据持久化到 config/user.json。
"""

import uuid
import re
from typing import Optional

from src.core.config import ConfigManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 内置指令的触发词（不允许自定义指令覆盖）
_BUILTIN_PHRASES = [
    "几点", "什么时间", "现在时间", "几点了", "现在几点",
    "打开浏览器", "开浏览器", "打开网页", "开网页",
]

# 允许的动作类型
ACTION_TYPES = ("open_url", "open_app")

# URL 协议白名单
_ALLOWED_URL_SCHEMES = ("http://", "https://")


def _normalize(text: str) -> str:
    """规范化文本：去标点、去空格、小写。"""
    text = text.strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    return text


def _generate_id() -> str:
    """生成短 ID。"""
    return uuid.uuid4().hex[:8]


class CustomCommand:
    """单个自定义指令。"""

    def __init__(
        self,
        id: str = None,
        phrases: list[str] = None,
        action_type: str = "open_url",
        action_target: str = "",
        response: str = "",
        enabled: bool = True,
    ):
        self.id = id or _generate_id()
        self.phrases = phrases or []
        self.action_type = action_type
        self.action_target = action_target
        self.response = response
        self.enabled = enabled

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "phrases": self.phrases,
            "action": {
                "type": self.action_type,
                "target": self.action_target,
            },
            "response": self.response,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CustomCommand":
        action = data.get("action", {})
        return cls(
            id=data.get("id", _generate_id()),
            phrases=data.get("phrases", []),
            action_type=action.get("type", "open_url"),
            action_target=action.get("target", ""),
            response=data.get("response", ""),
            enabled=data.get("enabled", True),
        )

    def matches(self, text: str) -> bool:
        """检查文本是否匹配此指令的任一触发词。"""
        if not self.enabled:
            return False
        norm_text = _normalize(text)
        for phrase in self.phrases:
            if _normalize(phrase) and _normalize(phrase) in norm_text:
                return True
        return False

    def is_conflict(self) -> bool:
        """检查触发词是否与内置指令冲突。"""
        for phrase in self.phrases:
            norm = _normalize(phrase)
            for builtin in _BUILTIN_PHRASES:
                if _normalize(builtin) in norm or norm in _normalize(builtin):
                    return True
        return False

    def validate(self) -> tuple[bool, str]:
        """验证指令数据。"""
        if not self.phrases:
            return False, "触发语句不能为空"
        if not self.action_type or self.action_type not in ACTION_TYPES:
            return False, f"不支持的动作类型: {self.action_type}"
        if not self.action_target:
            return False, "动作目标不能为空"
        if self.action_type == "open_url":
            if not any(self.action_target.startswith(s) for s in _ALLOWED_URL_SCHEMES):
                return False, "只支持 http/https 链接"
        if self.action_type == "open_app":
            from pathlib import Path
            if not Path(self.action_target).exists():
                return False, "应用路径不存在"
        if self.is_conflict():
            return False, "触发词与内置指令冲突"
        return True, ""


class CustomCommandManager:
    """自定义语音指令管理器。"""

    _CONFIG_KEY = "custom_voice_commands"

    def __init__(self):
        self._config = ConfigManager()
        self._commands: list[CustomCommand] = []
        self._load()
        logger.debug(
            "CustomCommandManager initialized (%d commands)", len(self._commands)
        )

    def _load(self):
        """从配置加载指令列表。"""
        raw = self._config.get(self._CONFIG_KEY, [])
        self._commands = []
        for item in raw:
            try:
                self._commands.append(CustomCommand.from_dict(item))
            except Exception:
                logger.warning("Skipping invalid custom command: %s", item)

    def _save(self):
        """保存指令列表到配置。"""
        data = [cmd.to_dict() for cmd in self._commands]
        self._config.set(self._CONFIG_KEY, data)
        self._config.save()

    def get_all(self) -> list[CustomCommand]:
        """获取所有指令。"""
        return list(self._commands)

    def get_enabled(self) -> list[CustomCommand]:
        """获取所有启用的指令。"""
        return [cmd for cmd in self._commands if cmd.enabled]

    def add(self, command: CustomCommand) -> tuple[bool, str]:
        """添加指令。返回 (是否成功, 错误信息)。"""
        ok, err = command.validate()
        if not ok:
            return False, err
        self._commands.append(command)
        self._save()
        logger.info("Custom command added: %s", command.id)
        return True, ""

    def update(self, command: CustomCommand) -> tuple[bool, str]:
        """更新指令。"""
        ok, err = command.validate()
        if not ok:
            return False, err
        for i, cmd in enumerate(self._commands):
            if cmd.id == command.id:
                self._commands[i] = command
                self._save()
                logger.info("Custom command updated: %s", command.id)
                return True, ""
        return False, "指令不存在"

    def delete(self, command_id: str) -> bool:
        """删除指令。"""
        for i, cmd in enumerate(self._commands):
            if cmd.id == command_id:
                self._commands.pop(i)
                self._save()
                logger.info("Custom command deleted: %s", command_id)
                return True
        return False

    def toggle(self, command_id: str, enabled: bool) -> bool:
        """启用/禁用指令。"""
        for cmd in self._commands:
            if cmd.id == command_id:
                cmd.enabled = enabled
                self._save()
                logger.info("Custom command %s: %s", command_id, "enabled" if enabled else "disabled")
                return True
        return False

    def match(self, text: str) -> Optional[CustomCommand]:
        """匹配文本，返回第一个匹配的启用指令。"""
        for cmd in self._commands:
            if cmd.matches(text):
                return cmd
        return None
