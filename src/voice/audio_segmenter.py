# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""音频分段模块

两种策略：
- fixed: 每 N 秒切一段
- vad:   基于能量阈值的静音检测
"""

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioSegmenter:
    """把连续音频块切分成一段段完整音频"""

    def __init__(
        self,
        mode: str = "fixed",
        sample_rate: int = 16000,
        sample_width: int = 2,
        max_seconds: float = 5.0,
        min_seconds: float = 1.0,
        silence_ms: int = 800,
        silence_threshold: int = 500,
        on_segment=None,
    ):
        self._mode = mode
        self._sample_rate = sample_rate
        self._sample_width = sample_width
        self._max_seconds = max_seconds
        self._min_seconds = min_seconds
        self._silence_ms = silence_ms
        self._silence_threshold = silence_threshold
        self._on_segment = on_segment

        self._buffer = bytearray()
        self._silence_run_ms = 0.0
        self._last_emit_time = 0.0

    def set_callback(self, callback):
        """callback(pcm_bytes: bytes)"""
        self._on_segment = callback

    def reset(self):
        self._buffer.clear()
        self._silence_run_ms = 0.0
        self._last_emit_time = 0.0

    def feed(self, pcm_bytes: bytes):
        """送入一块音频"""
        if not pcm_bytes:
            return

        self._buffer.extend(pcm_bytes)

        block_ms = self._block_duration_ms(pcm_bytes)
        self._last_emit_time += block_ms

        if self._mode == "vad":
            if self._is_silent(pcm_bytes):
                self._silence_run_ms += block_ms
            else:
                self._silence_run_ms = 0.0

            buffered_ms = self._buffer_duration_ms()
            # 静音结束且缓冲足够长
            if (
                self._silence_run_ms >= self._silence_ms
                and buffered_ms >= self._min_seconds * 1000
            ):
                self._emit()
                return

        # 达到最大时长，强制切
        if self._buffer_duration_ms() >= self._max_seconds * 1000:
            self._emit()

    def flush(self):
        """强制送出当前缓冲（停止时调用）"""
        if self._buffer_duration_ms() >= self._min_seconds * 1000:
            self._emit()
        else:
            self._buffer.clear()

    def _emit(self):
        if not self._buffer:
            return
        audio = bytes(self._buffer)
        self._buffer.clear()
        self._silence_run_ms = 0.0
        self._last_emit_time = 0.0
        if self._on_segment:
            try:
                self._on_segment(audio)
            except Exception:
                logger.exception("Error in segment callback")

    def _block_duration_ms(self, pcm_bytes: bytes) -> float:
        frames = len(pcm_bytes) / (self._sample_width * 1)
        return frames / self._sample_rate * 1000.0

    def _buffer_duration_ms(self) -> float:
        return self._block_duration_ms(bytes(self._buffer))

    def _is_silent(self, pcm_bytes: bytes) -> bool:
        """基于平均绝对值的简单能量检测。"""
        if not pcm_bytes:
            return True
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        except Exception:
            logger.exception("Failed to parse audio block")
            return False
        if samples.size == 0:
            return True
        return int(np.abs(samples).max()) < self._silence_threshold
