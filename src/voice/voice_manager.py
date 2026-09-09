# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音管理器模块

管理语音唤醒系统的生命周期。
与 EventBus 集成，发布唤醒事件。
"""

from PySide6.QtCore import QObject, Signal

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
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

        self._detector = None
        self._enabled = False
        self._available = False

        logger.debug("VoiceWakeManager initialized")

    def try_enable(self, enable: bool):
        """尝试启用或禁用语音唤醒，并返回是否成功"""
        if enable:
            if self.start():
                self.permission_changed.emit(True)
                return True
            else:
                self.permission_changed.emit(False)
                return False
        else:
            self.stop()
            self.permission_changed.emit(False)
            return True

    def start(self) -> bool:
        """启动语音唤醒。"""
        # 检查配置是否启用
        self._enabled = self._config.get("voice_wake.enabled", True)
        if not self._enabled:
            logger.info("Voice wake disabled by config")
            return False

        # 初始化检测器
        try:
            from src.voice.wake_detector import WakeDetector

            self._detector = WakeDetector()
            self._detector.set_callback(self._on_wake_detected)

            if self._detector.start():
                self._available = True
                logger.info("Voice wake started")
                return True
            else:
                logger.warning("Voice wake failed to start")
                self._available = False

        except Exception:
            logger.exception("Failed to initialize voice wake")
            self._available = False
            return False

    def stop(self):
        """停止语音唤醒。"""
        if self._detector:
            self._detector.stop()
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

    def get_debug_info(self) -> dict:
        """获取调试信息。"""
        return {
            "enabled": self._enabled,
            "available": self._available,
            "running": self.is_running,
        }
