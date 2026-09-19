# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""音频分段模块

两种策略：
- fixed: 每 N 秒切一段（仅供对照测试）
- vad:   基于 RMS 能量的静音检测

设计要点：
- 只有缓冲中已经出现过语音（_has_speech=True）才允许切分，
  避免切出整段纯静音的音频浪费推理
- RMS 能量检测比峰值检测更能抵抗突发噪声
- max_seconds 默认放宽到 15s，保证情感表达的语义完整性
"""

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioSegmenter:
    """把连续音频块切分成一段段完整音频"""

    def __init__(
        self,
        mode: str = "vad",
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
        max_seconds: float = 15.0,  # 情感分析建议 10~30s
        min_seconds: float = 1.0,
        silence_ms: int = 700,
        silence_rms_threshold: int = 400,  # int16 尺度下的 RMS 阈值
        on_segment=None,
    ):
        self._mode = mode
        self._sample_rate = sample_rate
        self._sample_width = sample_width
        self._channels = channels
        self._max_seconds = max_seconds
        self._min_seconds = min_seconds
        self._silence_ms = silence_ms
        self._silence_rms_threshold = silence_rms_threshold
        self._on_segment = on_segment

        self._buffer = bytearray()
        self._silence_run_ms = 0.0
        self._has_speech = False

    def set_callback(self, callback):
        """callback(pcm_bytes: bytes)"""
        self._on_segment = callback

    def reset(self):
        self._buffer.clear()
        self._silence_run_ms = 0.0
        self._has_speech = False

    def feed(self, pcm_bytes: bytes):
        """送入一块音频"""
        if not pcm_bytes:
            return

        self._buffer.extend(pcm_bytes)

        block_ms = self._block_duration_ms(pcm_bytes)
        is_silent = self._is_silent(pcm_bytes)

        if is_silent:
            self._silence_run_ms += block_ms
        else:
            self._silence_run_ms = 0.0
            self._has_speech = True

        buffered_ms = self._buffer_duration_ms()

        # VAD 模式：静音持续足够长 + 缓冲已包含语音 + 缓冲达到最小时长
        if self._mode == "vad":
            if (
                self._has_speech
                and self._silence_run_ms >= self._silence_ms
                and buffered_ms >= self._min_seconds * 1000
            ):
                self._emit()
                return

        # 达到最大时长，强制切
        if buffered_ms >= self._max_seconds * 1000:
            if self._has_speech:
                self._emit()
            else:
                # 整段都是静音，直接丢弃
                self._discard()

    def flush(self):
        """强制送出当前缓冲（停止时调用）"""
        if (
            self._has_speech
            and self._buffer_duration_ms() >= self._min_seconds * 1000
        ):
            self._emit()
        else:
            self._discard()

    def _emit(self):
        if not self._buffer:
            return
        audio = bytes(self._buffer)
        rms = self._calc_rms(audio)
        self._buffer.clear()
        self._silence_run_ms = 0.0
        self._has_speech = False
        if self._on_segment:
            try:
                self._on_segment(audio, rms)
            except Exception:
                logger.exception("Error in segment callback")

    def _discard(self):
        self._buffer.clear()
        self._silence_run_ms = 0.0
        self._has_speech = False

    def _block_duration_ms(self, pcm_bytes: bytes) -> float:
        frames = len(pcm_bytes) / (self._sample_width * self._channels)
        return frames / self._sample_rate * 1000.0

    def _buffer_duration_ms(self) -> float:
        return self._block_duration_ms(bytes(self._buffer))

    def _is_silent(self, pcm_bytes: bytes) -> bool:
        """基于 RMS 能量的静音检测"""
        if not pcm_bytes:
            return True
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        except Exception:
            logger.exception("Failed to parse audio block")
            return False
        if samples.size == 0:
            return True

        # 使用 float32 计算 RMS，避免 int16 平方溢出
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        return rms < self._silence_rms_threshold

    def _calc_rms(self, pcm_bytes: bytes) -> float:
        """计算整段音频的平均 RMS 能量（0.0 ~ 32767.0）"""
        if not pcm_bytes:
            return 0.0
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        except Exception:
            return 0.0
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
