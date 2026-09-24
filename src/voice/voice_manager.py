# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音情绪管理器

对外唯一入口，编排：
AudioCapture -> AudioSegmenter -> Provider -> EmotionParser -> EventBus

适配点：
- 支持 assemblyai / sensevoice / hybrid 三种 provider；hybrid 同时启用
  云端与本地 Provider，由 HybridVoiceProvider 按语言合并结果
- 默认分段参数向情感分析场景调优（max_seconds 从 5s 放宽到 15s）
- pause 时重置 segmenter，避免恢复后残留音频与新音频拼接
- 使用 ThreadPoolExecutor 管理分析任务，配合 BoundedSemaphore 限制并发，
  避免 segment 产生速度超过推理速度时任务无限堆积
"""

import concurrent.futures
import threading

from PySide6.QtCore import QObject, Signal

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)

#: Provider（SenseVoice / AssemblyAI 情绪分析）期望的目标采样率
TARGET_SAMPLE_RATE = 16000


class VoiceManager(QObject):
    """语音情绪识别生命周期管理"""

    state_changed = Signal(bool)  # True=running, False=stopped

    # 并发分析上限：超过则丢弃新 segment，避免 CPU 打满
    # AssemblyAI 轮询耗时较长（30~60s/segment），4 不够用会导致频繁丢弃
    # 可通过 voice.max_concurrent_analyze 配置覆盖
    MAX_CONCURRENT_ANALYZE = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ConfigManager()
        self._event_bus = EventBus()

        self._capture = None
        self._segmenter = None
        self._provider = None
        self._parser = None
        self._executor = None
        self._analyze_semaphore = None

        # 指令管理器
        from src.voice.commands import CommandManager
        self._command_manager = CommandManager()
        self._command_manager.register_builtin_actions()

        self._running = False
        self._provider_name = "assemblyai"
        self._sample_rate = 16000
        self._channels = 1
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
        sample_rate = self._config.get("voice.sample_rate", 16000)
        channels = self._config.get("voice.channels", 1)

        self._provider_name = provider_name
        self._sample_rate = sample_rate
        self._channels = channels

        if not self._build_provider(provider_name, sample_rate, channels):
            return False

        from src.voice.audio_capture import AudioCapture
        from src.voice.emotion_parser import EmotionParser

        self._parser = EmotionParser(
            min_confidence=self._config.get("voice.min_confidence", 0.5),
            # 情绪映射可从配置覆盖，缺省时使用内置默认映射
            emotion_map=self._config.get("voice.emotion_map"),
            sentiment_map=self._config.get("voice.sentiment_map"),
        )

        # 情感分析场景：分段参数默认放宽
        self._create_segmenter(sample_rate, channels)

        # 线程池负责执行分析任务，信号量限制排队数量
        self._max_concurrent = self._config.get(
            "voice.max_concurrent_analyze", self.MAX_CONCURRENT_ANALYZE
        )
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_concurrent,
            thread_name_prefix="VoiceAnalyze",
        )
        self._analyze_semaphore = threading.BoundedSemaphore(
            self._max_concurrent
        )

        self._capture = AudioCapture(
            sample_rate=sample_rate,
            channels=channels,
        )
        self._capture.set_callback(self._on_audio)

        if not self._capture.start():
            logger.error(
                "音频采集启动失败，请检查麦克风是否支持 %dHz/%dch",
                sample_rate,
                channels,
            )
            self._cleanup(close_provider=True, shutdown_executor=True)
            return False

        # 校验设备实际采样率，必要时按实际值重建分段器与 Provider
        if not self._ensure_sample_rate(sample_rate, channels):
            self._capture.stop()
            self._cleanup(close_provider=True, shutdown_executor=True)
            return False

        self._running = True
        self.state_changed.emit(True)
        logger.info(
            "VoiceManager started (provider=%s, %dHz)",
            provider_name,
            sample_rate,
        )
        return True

    def stop(self):
        if not self._running and self._executor is None:
            return

        self._running = False
        if self._capture:
            self._capture.stop()
        if self._segmenter:
            self._segmenter.flush()

        executor = self._executor
        self._executor = None
        if executor is not None:
            # 等待正在执行的任务结束，并取消尚未开始的任务
            executor.shutdown(wait=True, cancel_futures=True)

        self._analyze_semaphore = None
        self._cleanup(close_provider=True)
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

    def _create_segmenter(self, sample_rate: int, channels: int):
        """按给定采样率创建分段器（采样率变化时用于重建）"""
        from src.voice.audio_segmenter import AudioSegmenter

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

    def _ensure_sample_rate(self, sample_rate: int, channels: int) -> bool:
        """校验设备实际采样率；不一致时按实际值重建，无法满足时停止启动

        Provider 依赖 16000Hz 输入，因此：
        - 实际采样率不是 16000Hz：明确报错并返回 False
        - 实际采样率是 16000Hz 但配置不是：按实际值重建分段器与 Provider
        """
        actual_rate = self._capture.actual_sample_rate
        if actual_rate is None:
            logger.error("无法获取音频设备实际采样率，语音模块停止启动")
            return False

        if actual_rate != sample_rate:
            logger.warning(
                "音频设备实际采样率 %dHz 与配置 %dHz 不一致",
                actual_rate,
                sample_rate,
            )

        if actual_rate != TARGET_SAMPLE_RATE:
            logger.error(
                "音频设备不支持 %dHz 目标采样率（实际 %dHz），"
                "AssemblyAI/SenseVoice 需要 %dHz，语音模块停止启动",
                TARGET_SAMPLE_RATE,
                actual_rate,
                TARGET_SAMPLE_RATE,
            )
            return False

        if actual_rate == sample_rate:
            return True

        # 设备回落到目标采样率：重建分段器与 Provider 以匹配
        self._sample_rate = actual_rate
        self._create_segmenter(actual_rate, channels)
        if self._provider is not None:
            try:
                self._provider.close()
            except Exception:
                logger.exception("Failed to close old provider")
            self._provider = None
        if not self._build_provider(
            self._provider_name, actual_rate, channels
        ):
            logger.error("按实际采样率 %dHz 重建 Provider 失败", actual_rate)
            return False
        logger.info(
            "Rebuilt segmenter/provider for actual sample rate %dHz",
            actual_rate,
        )
        return True

    def _create_assemblyai(self, sample_rate: int, channels: int):
        """按配置创建 AssemblyAI Provider"""
        from src.voice.providers.assemblyai_provider import (
            AssemblyAIProvider,
        )

        return AssemblyAIProvider(
            api_key=(
                self._config.get("voice.assemblyai.api_key")
                or self._config.get("voice.api_key", "")
            ),
            language=(
                self._config.get("voice.assemblyai.language")
                or self._config.get("voice.language", "en")
            ),
            sample_rate=sample_rate,
            channels=channels,
            timeout=self._config.get("voice.assemblyai.timeout", 60),
        )

    def _create_sensevoice(self, sample_rate: int, channels: int):
        """按配置创建 SenseVoice Provider"""
        from src.voice.providers.sensevoice_gguf_provider import (
            SenseVoiceGGUFProvider,
        )

        return SenseVoiceGGUFProvider(
            exe_path=self._config.get_path("voice.sensevoice.exe_path"),
            model_path=self._config.get_path(
                "voice.sensevoice.model_path"
            ),
            sample_rate=sample_rate,
            channels=channels,
            timeout=self._config.get("voice.sensevoice.timeout", 30.0),
            n_threads=self._config.get("voice.sensevoice.n_threads", 8),
        )

    def _build_provider(
        self, name: str, sample_rate: int = 16000, channels: int = 1
    ) -> bool:
        if self._provider is not None:
            return True

        if name == "hybrid":
            from src.voice.providers.hybrid_provider import (
                HybridVoiceProvider,
            )

            assemblyai = self._create_assemblyai(sample_rate, channels)
            sensevoice = self._create_sensevoice(sample_rate, channels)
            provider = HybridVoiceProvider(
                assemblyai_provider=assemblyai,
                sensevoice_provider=sensevoice,
                allow_partial=self._config.get(
                    "voice.hybrid.allow_partial_provider", False
                ),
                max_workers=self._config.get("voice.hybrid.max_workers", 2),
            )
            if not provider.is_ready():
                logger.error(
                    "Hybrid provider not ready "
                    "(assemblyai_ready=%s, sensevoice_ready=%s)",
                    assemblyai.is_ready(),
                    sensevoice.is_ready(),
                )
                return False
            self._provider = provider
            return True

        if name == "sensevoice":
            provider = self._create_sensevoice(sample_rate, channels)
            if not provider.is_ready():
                logger.error("SenseVoice provider not ready")
                return False
            self._provider = provider
            return True

        if name == "assemblyai":
            provider = self._create_assemblyai(sample_rate, channels)
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

    def _on_segment(self, audio_bytes: bytes, rms: float):
        """收到一段完整音频，提交到线程池异步分析"""
        if not audio_bytes or not self._provider:
            return

        executor = self._executor
        semaphore = self._analyze_semaphore
        if executor is None or semaphore is None:
            return

        if not semaphore.acquire(blocking=False):
            logger.warning(
                "Analyze queue full (%d), dropping segment",
                getattr(self, "_max_concurrent", self.MAX_CONCURRENT_ANALYZE),
            )
            return

        try:
            future = executor.submit(self._analyze, audio_bytes, rms)
        except RuntimeError:
            # 线程池已关闭（停止过程中）
            semaphore.release()
            logger.warning("Analyze executor already stopped, drop segment")
            return
        future.add_done_callback(lambda _future: semaphore.release())

    def _analyze(self, audio_bytes: bytes, rms: float):
        try:
            raw = self._provider.transcribe_and_analyze(audio_bytes)
            parsed = self._parser.parse(raw)
            parsed["energy"] = rms
            self._publish(parsed)
        except Exception:
            logger.exception("Voice analyze failed")

    def _publish(self, parsed: dict):
        if not parsed.get("text"):
            return

        text = parsed.get("text", "")
        emotion = parsed.get("emotion", "UNKNOWN")
        sentiment = parsed.get("sentiment", "UNKNOWN")
        confidence = parsed.get("confidence", 0.0)
        energy = parsed.get("energy", 0.0)
        language = parsed.get("language", "UNKNOWN")
        event = parsed.get("event", "UNKNOWN")
        segments = parsed.get("segments", [])

        # 检查指令
        action = self._command_manager.process_text(text)
        if action:
            # 指令已处理，发射指令事件
            self._event_bus.emit("voice.command_detected", {
                "source": "voice",
                "text": text,
                "action": action,
                "emotion": emotion,
                "sentiment": sentiment,
                "confidence": confidence,
                "energy": energy,
                "language": language,
            })
            logger.info(
                "[Voice Command] action=%s | %s",
                action,
                text,
            )
            return

        # 正常情绪检测
        payload = {
            "source": "voice",
            "provider": self._provider.name if self._provider else "unknown",
            "emotion_source": parsed.get("emotion_source", "unknown"),
            "text": text,
            "emotion": emotion,
            "sentiment": sentiment,
            "confidence": confidence,
            "energy": energy,
            "language": language,
            "event": event,
            "segments": segments,
            "is_listening": self._command_manager.is_listening(),
        }

        self._event_bus.emit("voice.emotion_detected", payload)
        logger.info(
            "[Voice Emotion] %s (%s, %.2f) energy=%.1f lang=%s "
            "event=%s source=%s listening=%s | %s",
            payload["emotion"],
            payload["sentiment"],
            payload["confidence"],
            payload["energy"],
            payload["language"],
            payload["event"],
            payload["emotion_source"],
            payload["is_listening"],
            payload["text"],
        )

    def _cleanup(
        self, close_provider: bool = False, shutdown_executor: bool = False
    ):
        if shutdown_executor and self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
        if close_provider and self._provider is not None:
            try:
                self._provider.close()
            except Exception:
                logger.exception("Failed to close voice provider")
            self._provider = None
        self._capture = None
        self._segmenter = None

    def get_debug_info(self) -> dict:
        return {
            "running": self._running,
            "provider": self._provider.name if self._provider else None,
            "provider_ready": (
                self._provider.is_ready() if self._provider else False
            ),
            "max_concurrent_analyze": getattr(
                self, "_max_concurrent", self.MAX_CONCURRENT_ANALYZE
            ),
            "command_manager": self._command_manager.get_debug_info(),
        }

    def get_command_manager(self):
        """获取指令管理器。"""
        return self._command_manager
