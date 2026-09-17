# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""麦克风采集模块

只负责把原始音频块通过回调吐出，不做分段、不做识别
"""

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioCapture:
    """打开一路麦克风输入流，把音频块推给回调"""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 1600,  # 100ms @ 16k
        device=None,
        latency: str = "low",
    ):
        self._sample_rate = sample_rate
        self._channels = channels
        self._blocksize = blocksize
        self._device = device
        self._latency = latency

        self._stream = None
        self._running = False
        self._callback = None
        self._actual_sample_rate = None

    def set_callback(self, callback):
        """设置音频块回调，签名：callback(pcm_bytes: bytes)"""
        self._callback = callback

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def actual_sample_rate(self):
        """实际生效的采样率（由 sounddevice 返回），未启动时为 None"""
        return self._actual_sample_rate

    def start(self) -> bool:
        if self._running:
            return True
        try:
            import sounddevice as sd
        except ImportError:
            logger.error(
                "sounddevice not installed. Run: pip install sounddevice"
            )
            return False

        try:
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=self._blocksize,
                dtype="int16",
                channels=self._channels,
                device=self._device,
                latency=self._latency,
                callback=self._on_audio,
            )
            self._stream.start()
            self._running = True
            self._actual_sample_rate = self._stream.samplerate
            logger.info(
                "Audio capture started (%dHz, %dch, device=%s)",
                self._actual_sample_rate,
                self._channels,
                self._device if self._device is not None else "default",
            )
            return True
        except Exception:
            logger.exception("Failed to start audio capture")
            self._stream = None
            return False

    def stop(self):
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._actual_sample_rate = None
        logger.info("Audio capture stopped")

    def list_devices(self):
        """返回可用输入设备列表，方便选择 device"""
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice not installed.")
            return []
        return sd.query_devices()

    def _on_audio(self, indata, frames, time_info, status):
        # 注：签名中参数不得修改
        if status:
            logger.warning("Audio status: %s", status)
        if self._callback:
            try:
                self._callback(bytes(indata))
            except Exception:
                logger.exception("Error in audio callback")
