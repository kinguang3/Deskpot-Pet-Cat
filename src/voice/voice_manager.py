# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音情绪管理器

对外唯一入口，编排：
AudioCapture -> AudioSegmenter -> Provider -> EmotionParser -> EventBus

适配点：
- 新增 sensevoice provider 分支，通过 SenseVoiceGGUFProvider 调用
  本地的 llama-funasr-sensevoice.exe
- 默认分段参数向情感分析场景调优（max_seconds 从 5s 放宽到 15s）
- pause 时重置 segmenter，避免恢复后残留音频与新音频拼接
- 限制并发分析线程数，避免 segment 产生速度超过推理速度时线程堆积
"""

import threading

from PySide6.QtCore import QObject, Signal

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceManager(QObject):
    """语音情绪识别生命周期管理"""

    state_changed = Signal(bool)  # True=running, False=stopped

    # 并发分析上限：超过则丢弃新 segment，避免 CPU 打满
    MAX_CONCURRENT_ANALYZE = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ConfigManager()
        self._event_bus = EventBus()

        self._capture = None
        self._segmenter = None
        self._provider = None
        self._parser = None

        self._running = False
        self._analyzing = 0
        self._lock = threading.Lock()

        logger.debug("VoiceManager initialized")

    # 生命周期

    def start(self) -> bool:
        if self._running:
            return True

        if not self._config.get("voice.enabled", False):
            logger.info("Voice module disabled by config")
            return False

        provider_name = self._config.get("voice.provider", "assemblyai")
        if not self._build_provider(provider_name):
            return False

        from src.voice.audio_capture import AudioCapture
        from src.voice.audio_segmenter import AudioSegmenter
        from src.voice.emotion_parser import EmotionParser

        sample_rate = self._config.get("voice.sample_rate", 16000)
        channels = self._config.get("voice.channels", 1)

        self._parser = EmotionParser(
            min_confidence=self._config.get("voice.min_confidence", 0.5)
        )

        # 情感分析场景：分段参数默认放宽
        self._segmenter = AudioSegmenter(
            mode=self._config.get("voice.segment_mode", "vad"),
            sample_rate=sample_rate,
            channels=channels,
            max_seconds=self._config.get("voice.segment_max_seconds", 15.0),
            min_seconds=self._config.get("voice.segment_min_seconds", 1.0),
            silence_ms=self._config.get("voice.segment_silence_ms", 700),
            silence_rms_threshold=self._config.get(
                "voice.segment_silence_rms_threshold", 400
            ),
            on_segment=self._on_segment,
        )

        self._capture = AudioCapture(
            sample_rate=sample_rate,
            channels=channels,
        )
        self._capture.set_callback(self._on_audio)

        if not self._capture.start():
            self._cleanup()
            return False

        self._running = True
        self.state_changed.emit(True)
        logger.info("VoiceManager started (provider=%s)", provider_name)
        return True

    def stop(self):
        if not self._running:
            return

        self._running = False
        if self._capture:
            self._capture.stop()
        if self._segmenter:
            self._segmenter.flush()

        self._cleanup()
        self.state_changed.emit(False)
        logger.info("VoiceManager stopped")

    def pause(self):
        if self._capture and self._capture.is_running:
            self._capture.stop()
            # 清空分段缓冲，避免恢复后残留音频与新音频拼接
            if self._segmenter:
                self._segmenter.reset()
            logger.debug("VoiceManager paused")

    def resume(self):
        if self._running and self._capture and not self._capture.is_running:
            self._capture.start()
            logger.debug("VoiceManager resumed")

    def is_running(self) -> bool:
        return self._running

    # 内部

    def _build_provider(self, name: str) -> bool:
        if self._provider is not None:
            return True

        if name == "sensevoice":
            from src.voice.providers.sensevoice_gguf_provider import (
                SenseVoiceGGUFProvider,
            )

            provider = SenseVoiceGGUFProvider(
                exe_path=self._config.get_path("voice.sensevoice.exe_path"),
                model_path=self._config.get_path(
                    "voice.sensevoice.model_path"
                ),
                vad_path=self._config.get_path("voice.sensevoice.vad_path"),
                sample_rate=self._config.get("voice.sample_rate", 16000),
                channels=self._config.get("voice.channels", 1),
                timeout=self._config.get("voice.sensevoice.timeout", 30.0),
            )
            if not provider.is_ready():
                logger.error("SenseVoice provider not ready")
                return False
            self._provider = provider
            return True

        if name == "assemblyai":
            from src.voice.providers.assemblyai_provider import (
                AssemblyAIProvider,
            )

            provider = AssemblyAIProvider(
                api_key=self._config.get("voice.api_key", ""),
                language=self._config.get("voice.language", "en"),
                sample_rate=self._config.get("voice.sample_rate", 16000),
                channels=self._config.get("voice.channels", 1),
            )
            if not provider.is_ready():
                logger.error("AssemblyAI provider not ready")
                return False
            self._provider = provider
            return True

        logger.error("Unknown voice provider: %s", name)
        return False

    def _on_audio(self, pcm_bytes: bytes):
        if not self._running or not self._segmenter:
            return
        try:
            self._segmenter.feed(pcm_bytes)
        except Exception:
            logger.exception("Error feeding audio to segmenter")

    def _on_segment(self, audio_bytes: bytes):
        """收到一段完整音频，异步分析"""
        if not audio_bytes or not self._provider:
            return

        with self._lock:
            if self._analyzing >= self.MAX_CONCURRENT_ANALYZE:
                logger.warning(
                    "Analyze queue full (%d), dropping segment",
                    self._analyzing,
                )
                return
            self._analyzing += 1

        threading.Thread(
            target=self._analyze,
            args=(audio_bytes,),
            daemon=True,
            name="VoiceAnalyze",
        ).start()

    def _analyze(self, audio_bytes: bytes):
        try:
            raw = self._provider.transcribe_and_analyze(audio_bytes)
            parsed = self._parser.parse(raw)
            self._publish(parsed)
        except Exception:
            logger.exception("Voice analyze failed")
        finally:
            with self._lock:
                self._analyzing -= 1

    def _publish(self, parsed: dict):
        if not parsed.get("text"):
            return

        payload = {
            "source": "voice",
            "provider": self._provider.name if self._provider else "unknown",
            "text": parsed.get("text", ""),
            "emotion": parsed.get("emotion", "UNKNOWN"),
            "sentiment": parsed.get("sentiment", "UNKNOWN"),
            "confidence": parsed.get("confidence", 0.0),
            "language": parsed.get("language", "UNKNOWN"),
            "event": parsed.get("event", "UNKNOWN"),
            "segments": parsed.get("segments", []),
        }

        self._event_bus.emit("voice.emotion_detected", payload)
        logger.info(
            "[Voice Emotion] %s (%s, %.2f) lang=%s event=%s | %s",
            payload["emotion"],
            payload["sentiment"],
            payload["confidence"],
            payload["language"],
            payload["event"],
            payload["text"],
        )

    def _cleanup(self):
        self._capture = None
        self._segmenter = None

    def get_debug_info(self) -> dict:
        return {
            "running": self._running,
            "analyzing": self._analyzing,
            "provider": self._provider.name if self._provider else None,
            "provider_ready": (
                self._provider.is_ready() if self._provider else False
            ),
        }
