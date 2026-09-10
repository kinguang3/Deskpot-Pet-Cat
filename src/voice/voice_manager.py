# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音管理器模块

管理语音唤醒系统的生命周期。
与 EventBus 集成，发布唤醒事件。
"""

from PySide6.QtCore import QObject, Signal

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.voice.command_parser import CommandParser, Intent
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceWakeManager(QObject):
    """语音唤醒管理器。

    职责：
    - 管理 WakeDetector 的生命周期
    - 与 EventBus 集成
    - 处理配置和启用/禁用
    """

    # 是否有权限
    permission_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ConfigManager()
        self._event_bus = EventBus()
        self._parser = CommandParser()

        self._detector = None
        self._enabled = False
        self._available = False

        logger.debug("VoiceWakeManager initialized")

    def try_enable(self, enable: bool) -> bool:
        """尝试启用或禁用语音唤醒，并返回是否成功"""
        if enable:
            # 强制将配置设为 True，覆盖之前可能的 False
            self._config.set("voice_wake.enabled", True)
            self._config.save()
            success = self.start()
            self._detector = None
            if success:
                self.permission_changed.emit(True)
            else:
                self.permission_changed.emit(False)
            return success
        else:
            self.stop()
            self._config.set("voice_wake.enabled", False)
            self._config.save()
            self.permission_changed.emit(False)
            return True

    def start(self) -> bool:
        """启动语音唤醒。"""
        # 清理残留 detector
        if self._detector is not None:
            self._detector.stop()
            self._detector = None

        # 检查配置是否启用
        if not self._config.get("voice_wake.enabled", True):
            logger.info("Voice wake disabled by config")
            return False

        # 初始化检测器
        try:
            from src.voice.wake_detector import WakeDetector

            self._detector = WakeDetector()
            self._detector.set_callback(self._on_wake_detected)
            self._detector.set_command_callback(self._on_command_detected)

            if self._detector.start():
                self._available = True
                logger.info("Voice wake started")
                return True
            else:
                logger.warning("Voice wake failed to start")
                self._available = False
                # 失败后确保 detector 被释放
                self._detector.stop()
                self._detector = None
                return False
        except Exception as e:
            logger.exception("Failed to initialize voice wake: %s", e)
            self._available = False
            if self._detector:
                self._detector.stop()
                self._detector = None
            return False

    def stop(self):
        """停止语音唤醒。"""
        if self._detector:
            self._detector.stop()
            self._detector = None
        self._available = False
        logger.info("Voice wake stopped")

    def pause(self):
        """暂停语音唤醒。"""
        if self._detector and self._detector.is_running:
            self._detector.stop()
            logger.debug("Voice wake paused")

    def resume(self):
        """恢复语音唤醒。"""
        if self._enabled and not self._available:
            self.start()

    def set_enabled(self, enabled: bool):
        """设置启用状态。"""
        self._enabled = enabled
        self._config.set("voice_wake.enabled", enabled)

        if enabled:
            self.start()
        else:
            self.stop()

    def check_permission(self) -> bool:
        """检查麦克风权限是否可用"""
        from src.voice.wake_detector import WakeDetector

        return WakeDetector.has_microphone()

    @property
    def is_running(self) -> bool:
        return self._available and self._detector.is_running

    @property
    def is_available(self) -> bool:
        return self._available

    def _on_wake_detected(self, text: str):
        """唤醒词检测到回调。"""
        logger.info("Wake phrase detected: %s", text)

        # 通过 EventBus 发布事件
        self._event_bus.emit(
            "voice.wake_detected",
            {
                "source": "voice",
                "text": text,
            },
        )
        logger.debug("Wake event emitted")

    def enter_command_mode(self):
        """进入命令窗口模式（唤醒后接收语音命令）。"""
        if self._detector:
            self._detector.enter_command_mode()

    def exit_command_mode(self):
        """退出命令窗口模式。"""
        if self._detector:
            self._detector.exit_command_mode()

    def set_command_mode(self, enabled: bool):
        """设置始终命令模式。

        开启后，非 sleep 状态下所有语音直接作为命令处理。
        """
        if self._detector:
            self._detector.set_always_command(enabled)

    def _on_command_detected(self, text: str):
        """命令窗口内识别到语音文本。"""
        logger.info("[Voice Command] %s", text)

        # 解析意图
        intent, data = self._parser.parse(text)

        # 通过 EventBus 发布命令事件
        self._event_bus.emit(
            "voice.command_detected",
            {
                "source": "voice",
                "intent": intent.value,
                "text": text,
            },
        )

    def get_debug_info(self) -> dict:
        """获取调试信息。"""
        return {
            "enabled": self._enabled,
            "available": self._available,
            "running": self.is_running,
        }
