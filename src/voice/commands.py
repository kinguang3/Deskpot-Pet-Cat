# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音指令管理模块

管理唤醒词检测和自定义指令匹配。
- Wake word detection: 识别唤醒词，进入聆听模式
- Custom commands: 匹配用户自定义指令并执行相应动作
"""

import time
from datetime import datetime
from typing import Optional, Callable

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 有外部副作用、会离开应用的动作：默认必须先说唤醒词。
# 理由：这类动作一旦被日常语音误触发，用户会直接看到浏览器被打开、
# 窗口被切走，属于明显的非预期副作用。而 show_time / play_dance
# 这类只在应用内生效的动作被误触发代价很低，因此保留直接触发。
WAKE_WORD_REQUIRED_ACTIONS = frozenset({"open_website"})

# 比较时忽略的字符：ASR 结果常带句末标点与空格，不去掉会让「精确匹配」
# 形同虚设（说「打开百度。」匹配不上「打开百度」）。
_IGNORED_CHARS = (
    " \t\r\n\u3000"          # 空格/制表/换行/全角空格
    "\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a"  # ，。！？、；：
    ",.!?;:~"                # 半角标点
    "\uff5e\u2026\u2014"     # ～…—
    "\"'"                   # 直引号
    "\u201c\u201d\u2018\u2019"  # 弯引号
    "()\uff08\uff09\u3010\u3011[]{}"  # 括号/方括号
)


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

    @staticmethod
    def _normalize(text: str) -> str:
        """归一化用于比较：小写 + 去掉空格与标点"""
        return "".join(
            ch for ch in text.lower() if ch not in _IGNORED_CHARS
        )

    @staticmethod
    def requires_wake_word(cmd: dict) -> bool:
        """该指令是否必须先唤醒

        显式配置 ``require_wake_word`` 优先；未配置时按动作风险分级：
        有外部副作用的动作默认需要唤醒词。
        """
        explicit = cmd.get("require_wake_word")
        if isinstance(explicit, bool):
            return explicit
        return cmd.get("action", "") in WAKE_WORD_REQUIRED_ACTIONS

    def match_command(
        self, text: str, allow_wake_required: bool = True
    ) -> Optional[dict]:
        """匹配文本中的自定义指令。

        Args:
            text: 识别文本
            allow_wake_required: 是否允许匹配「必须先唤醒」的指令。
                直接匹配路径（未唤醒）应传 False，避免日常语音误触发
                打开浏览器之类的外部动作。
        """
        if not text:
            return None

        text_norm = self._normalize(text)
        if not text_norm:
            return None

        for cmd in self._commands:
            trigger = cmd.get("trigger", "")
            if not trigger:
                continue

            if not allow_wake_required and self.requires_wake_word(cmd):
                logger.debug(
                    "跳过需唤醒的指令 '%s'（当前未处于唤醒状态）", trigger
                )
                continue

            trigger_norm = self._normalize(trigger)
            if not trigger_norm:
                continue

            # 支持精确匹配和包含匹配
            match_type = cmd.get("match_type", "contains")
            if match_type == "exact":
                if text_norm == trigger_norm:
                    return cmd
            else:
                # contains (默认)
                if trigger_norm in text_norm:
                    return cmd

        return None

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
        self._event_bus.emit("command.play_animation", {"animation": "dance"})

    def handle_show_status(self, context: dict):
        """显示状态信息。"""
        self._event_bus.emit("command.show_status", {})

    def handle_open_website(self, context: dict):
        """打开网站。"""
        url = context.get("url", "")
        if url:
            # 确保 URL 有协议前缀
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            self._event_bus.emit("command.open_website", {"url": url})
            logger.info("Opening website: %s", url)
        else:
            logger.warning("No URL provided for open_website action")

    def handle_show_dialogue(self, context: dict):
        """显示自定义对话文本。"""
        text = context.get("text", "")
        if text:
            self._event_bus.emit("command.show_dialogue", {"text": text})
            logger.info("Showing custom dialogue: %s", text)

    def register_builtin_actions(self):
        """注册所有内置动作处理器。"""
        self.register_action("show_time", self.handle_show_time)
        self.register_action("show_date", self.handle_show_date)
        self.register_action("show_greeting", self.handle_show_greeting)
        self.register_action("play_happy", self.handle_play_happy)
        self.register_action("play_dance", self.handle_play_dance)
        self.register_action("show_status", self.handle_show_status)
        self.register_action("open_website", self.handle_open_website)
        self.register_action("show_dialogue", self.handle_show_dialogue)

    # ─── 配置管理 ───

    def reload(self):
        """重新从配置加载唤醒词与指令（设置面板保存后调用）。"""
        self._wake_words: list[str] = self._config.get(
            "voice.commands.wake_words", ["hey nina", "小猫", "nina"]
        )
        self._wake_timeout_ms: int = self._config.get(
            "voice.commands.wake_timeout_ms", 5000
        )
        self._commands: list[dict] = self._config.get(
            "voice.commands.custom", []
        )
        logger.info(
            "CommandManager reloaded (wake_words=%s, commands=%d)",
            self._wake_words,
            len(self._commands),
        )

    # ─── 状态管理 ───

    def is_listening(self) -> bool:
        """是否处于聆听模式。"""
        return self._is_listening

    def set_listening(self, listening: bool):
        """设置聆听模式状态。"""
        self._is_listening = listening
        if listening:
            self._last_wake_time = time.time() * 1000
        logger.debug("Listening mode: %s", listening)

    def is_wake_timeout(self) -> bool:
        """检查唤醒是否超时。"""
        if not self._is_listening:
            return False
        elapsed = (time.time() * 1000) - self._last_wake_time
        return elapsed > self._wake_timeout_ms

    # ─── 完整处理流程 ───

    def process_text(self, text: str) -> Optional[str]:
        """处理识别文本，返回动作类型或 None。

        流程：
        1. 直接匹配指令（无需唤醒词）；但会跳过「必须先唤醒」的指令，
           防止日常语音（比如说到「打开空调」）误触发打开浏览器；
        2. 有唤醒词时进入/刷新聆听模式，用于随后的连续指令；
        3. 聆听模式下匹配后续指令，超时自动退出聆听。
        """
        if not text:
            return None

        # 1) 直接匹配指令（唤醒词不是必需条件，但受风险分级约束）
        cmd = self.match_command(text, allow_wake_required=False)
        if cmd:
            action = self._build_and_execute(cmd, text)
            # 说了一个指令，顺带刷新聆听窗口，便于连续下达
            self.set_listening(True)
            return action

        # 2) 检查唤醒词
        if self.check_wake_word(text):
            self.set_listening(True)
            # 移除唤醒词，提取剩余部分作为指令
            text_after_wake = self._remove_wake_word(text)
            if text_after_wake:
                cmd = self.match_command(text_after_wake)
                if cmd:
                    action = self._build_and_execute(cmd, text_after_wake)
                    return action
            return "wake_detected"

        # 3) 聆听模式：匹配后续指令
        if self._is_listening:
            if self.is_wake_timeout():
                self.set_listening(False)
                return None

            cmd = self.match_command(text)
            if cmd:
                action = self._build_and_execute(cmd, text)
                self.set_listening(False)
                return action

        return None

    def _build_and_execute(self, cmd: dict, said: str) -> str:
        """按指令动作构造上下文并执行，返回动作名。"""
        action = cmd.get("action", "")
        context = {"text": said}
        # 如果是 open_website，传递 URL
        if action == "open_website":
            context["url"] = cmd.get("custom_url", "")
        # 如果是 show_dialogue，传递自定义文本
        elif action == "show_dialogue":
            context["text"] = cmd.get("custom_text", said)
        self.execute_action(action, context)
        return action

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
