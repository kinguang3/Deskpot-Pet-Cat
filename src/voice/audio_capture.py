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
        self._actual_channels = None

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

    @property
    def actual_channels(self):
        """实际生效的声道数（由 sounddevice 返回），未启动时为 None"""
        return self._actual_channels

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
            actual_channels = getattr(self._stream, "channels", self._channels)
            self._actual_channels = actual_channels
            if self._actual_sample_rate != self._sample_rate:
                logger.warning(
                    "Audio capture actual sample rate %dHz differs from "
                    "requested %dHz",
                    self._actual_sample_rate,
                    self._sample_rate,
                )
            # Provider（SenseVoice/AssemblyAI）只吃单声道。这里不做下混，
            # 因为多声道交错 PCM 送进 RMS 分段和 ASR 只会得到错误结果，
            # 且错得没有任何提示——直接失败让用户去系统里把麦克风设为单声道。
            if actual_channels != 1:
                logger.error(
                    "Audio device reports %d channels; voice pipeline "
                    "requires mono (1 channel). Set the microphone to mono "
                    "in system sound settings.",
                    actual_channels,
                )
                self._running = False
                self._close_stream()
                return False
            logger.info(
                "Audio capture started (%dHz, %dch, device=%s)",
                self._actual_sample_rate,
                actual_channels,
                self._device if self._device is not None else "default",
            )
            return True
        except Exception:
            logger.exception("Failed to start audio capture")
            # 关键：RawInputStream 可能已创建成功但 start() 失败，此时对象
            # 仍持有声卡句柄。必须显式关闭，否则设备被永久占用，
            # 后续 start() 会持续失败。
            self._close_stream()
            return False

    def stop(self):
        self._running = False
        self._close_stream()
        self._actual_sample_rate = None
        self._actual_channels = None
        logger.info("Audio capture stopped")

    def _close_stream(self):
        """关闭并释放音频流，保证 close() 一定被调用

        stop() 失败不应阻止 close()：否则声卡句柄泄漏。
        """
        stream = self._stream
        if stream is None:
            return
        self._stream = None
        try:
            stream.stop()
        except Exception:
            logger.debug("Audio stream stop() failed (ignored)", exc_info=True)
        finally:
            try:
                stream.close()
            except Exception:
                logger.warning("Audio stream close() failed", exc_info=True)

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
