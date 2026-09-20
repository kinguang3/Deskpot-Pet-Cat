# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音指令管理模块

管理唤醒词检测和自定义指令匹配。
- Wake word detection: 识别唤醒词，进入聆听模式
- Custom commands: 匹配用户自定义指令并执行相应动作
"""

import re
from datetime import datetime
from typing import Optional, Callable

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CommandManager:
    """语音指令管理器。"""

    def __init__(self, parent=None):
        self._config = ConfigManager()
        self._event_bus = EventBus()

        # 唤醒词配置
        self._wake_words: list[str] = self._config.get(
            "voice.commands.wake_words", ["hey nina", "小猫", "nina"]
        )
        self._wake_timeout_ms: int = self._config.get(
            "voice.commands.wake_timeout_ms", 5000
        )

        # 自定义指令
        self._commands: list[dict] = self._config.get(
            "voice.commands.custom", []
        )

        # 状态
        self._is_listening = False
        self._last_wake_time = 0

        # 动作处理器注册
        self._action_handlers: dict[str, Callable] = {}

        logger.debug(
            "CommandManager initialized (wake_words=%s, commands=%d)",
            self._wake_words,
            len(self._commands),
        )

    # ─── 唤醒词检测 ───

    def check_wake_word(self, text: str) -> bool:
        """检查文本中是否包含唤醒词。"""
        if not text:
            return False

        text_lower = text.lower().strip()

        for wake_word in self._wake_words:
            if wake_word.lower() in text_lower:
                logger.info("Wake word detected: '%s' in '%s'", wake_word, text)
                return True

        return False

    # ─── 指令匹配 ───

    def match_command(self, text: str) -> Optional[dict]:
        """匹配文本中的自定义指令。"""
        if not text:
            return None

        text_lower = text.lower().strip()

        for cmd in self._commands:
            trigger = cmd.get("trigger", "").lower()
            if not trigger:
                continue

            # 支持精确匹配和包含匹配
            match_type = cmd.get("match_type", "contains")
            if match_type == "exact":
                if text_lower == trigger:
                    return cmd
            else:
                # contains (默认)
                if trigger in text_lower:
                    return cmd

        return None

    # ─── 动作执行 ───

    def execute_action(self, action: str, context: dict = None) -> bool:
        """执行指定动作。"""
        handler = self._action_handlers.get(action)
        if handler:
            try:
                handler(context or {})
                logger.info("Action executed: %s", action)
                return True
            except Exception:
                logger.exception("Action execution failed: %s", action)
                return False

        logger.warning("Unknown action: %s", action)
        return False

    def register_action(self, action: str, handler: Callable):
        """注册动作处理器。"""
        self._action_handlers[action] = handler
        logger.debug("Action registered: %s", action)

    # ─── 内置动作处理器 ───

    def handle_show_time(self, context: dict):
        """显示当前时间。"""
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        self._event_bus.emit("command.show_dialogue", {"text": f"现在是 {time_str}"})

    def handle_show_date(self, context: dict):
        """显示当前日期。"""
        now = datetime.now()
        date_str = now.strftime("%Y年%m月%d日")
        self._event_bus.emit("command.show_dialogue", {"text": f"今天是 {date_str}"})

    def handle_show_greeting(self, context: dict):
        """显示问候语。"""
        hour = datetime.now().hour
        if 5 <= hour < 9:
            greeting = "早上好！新的一天开始了~"
        elif 9 <= hour < 17:
            greeting = "下午好~"
        elif 17 <= hour < 21:
            greeting = "晚上好~"
        else:
            greeting = "这么晚了还不睡吗？"
        self._event_bus.emit("command.show_dialogue", {"text": greeting})

    def handle_play_happy(self, context: dict):
        """播放开心动画。"""
        self._event_bus.emit("command.play_animation", {"animation": "happy"})

    def handle_play_dance(self, context: dict):
        """播放跳舞动画。"""
        self._event_bus.emit("command.play_animation", {"animation": "walk"})

    def handle_show_status(self, context: dict):
        """显示状态信息。"""
        self._event_bus.emit("command.show_status", {})

    def register_builtin_actions(self):
        """注册所有内置动作处理器。"""
        self.register_action("show_time", self.handle_show_time)
        self.register_action("show_date", self.handle_show_date)
        self.register_action("show_greeting", self.handle_show_greeting)
        self.register_action("play_happy", self.handle_play_happy)
        self.register_action("play_dance", self.handle_play_dance)
        self.register_action("show_status", self.handle_show_status)

    # ─── 配置管理 ───

    def get_wake_words(self) -> list[str]:
        """获取唤醒词列表。"""
        return self._wake_words.copy()

    def set_wake_words(self, words: list[str]):
        """设置唤醒词列表。"""
        self._wake_words = words
        self._config.set("voice.commands.wake_words", words)
        logger.info("Wake words updated: %s", words)

    def get_commands(self) -> list[dict]:
        """获取自定义指令列表。"""
        return self._commands.copy()

    def add_command(self, trigger: str, action: str, description: str = ""):
        """添加自定义指令。"""
        cmd = {
            "trigger": trigger,
            "action": action,
            "description": description,
        }
        self._commands.append(cmd)
        self._config.set("voice.commands.custom", self._commands)
        logger.info("Command added: %s -> %s", trigger, action)

    def remove_command(self, trigger: str):
        """删除自定义指令。"""
        self._commands = [
            cmd for cmd in self._commands if cmd.get("trigger") != trigger
        ]
        self._config.set("voice.commands.custom", self._commands)
        logger.info("Command removed: %s", trigger)

    def clear_commands(self):
        """清空所有自定义指令。"""
        self._commands.clear()
        self._config.set("voice.commands.custom", self._commands)
        logger.info("All commands cleared")

    # ─── 状态管理 ───

    def is_listening(self) -> bool:
        """是否处于聆听模式。"""
        return self._is_listening

    def set_listening(self, listening: bool):
        """设置聆听模式状态。"""
        self._is_listening = listening
        if listening:
            self._last_wake_time = __import__("time").time() * 1000
        logger.debug("Listening mode: %s", listening)

    def is_wake_timeout(self) -> bool:
        """检查唤醒是否超时。"""
        if not self._is_listening:
            return False
        import time
        elapsed = (time.time() * 1000) - self._last_wake_time
        return elapsed > self._wake_timeout_ms

    # ─── 完整处理流程 ───

    def process_text(self, text: str) -> Optional[str]:
        """处理识别文本，返回动作类型或 None。"""
        if not text:
            return None

        # 检查唤醒词
        if self.check_wake_word(text):
            self.set_listening(True)
            # 移除唤醒词，提取剩余部分作为指令
            text_after_wake = self._remove_wake_word(text)
            if text_after_wake:
                cmd = self.match_command(text_after_wake)
                if cmd:
                    self.execute_action(cmd.get("action", ""), {"text": text_after_wake})
                    return cmd.get("action")
            return "wake_detected"

        # 如果在聆听模式，检查指令
        if self._is_listening:
            if self.is_wake_timeout():
                self.set_listening(False)
                return None

            cmd = self.match_command(text)
            if cmd:
                self.execute_action(cmd.get("action", ""), {"text": text})
                self.set_listening(False)
                return cmd.get("action")

        return None

    def _remove_wake_word(self, text: str) -> str:
        """从文本中移除唤醒词。"""
        text_lower = text.lower()
        for wake_word in self._wake_words:
            wake_lower = wake_word.lower()
            if wake_lower in text_lower:
                idx = text_lower.index(wake_lower)
                remaining = text[idx + len(wake_word):].strip()
                return remaining
        return text

    # ─── 调试 ───

    def get_debug_info(self) -> dict:
        """获取调试信息。"""
        return {
            "wake_words": self._wake_words,
            "commands_count": len(self._commands),
            "is_listening": self._is_listening,
            "actions_registered": list(self._action_handlers.keys()),
        }
