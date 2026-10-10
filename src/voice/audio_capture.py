# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""麦克风采集模块

只负责把原始音频块通过回调吐出，不做分段、不做识别。

- 可通过 ``voice.input_device`` 选择具体麦克风（按名称匹配，重启不漂移），
  缺省用系统默认输入。
- 若所选设备是多声道（如麦克风阵列），自动下混为单声道再吐出：
  直接按单声道请求有时只会拿到第 0 声道（静音），白费一个能用的麦。
"""

import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


def input_devices() -> list[dict]:
    """列出所有可用的输入设备（含声道数），供设置页展示。"""
    try:
        import sounddevice as sd
    except ImportError:
        return []
    devices = []
    for index, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] > 0:
            devices.append(
                {
                    "index": index,
                    "name": info["name"],
                    "channels": info["max_input_channels"],
                    "hostapi": info["hostapi"],
                    "default_samplerate": info["default_samplerate"],
                }
            )
    return devices


def resolve_input_device(configured) -> int | None:
    """把配置里的设备名/索引解析为 sounddevice 可用的 device 参数。

    返回 None 表示使用系统默认。按设备名（子串匹配）而不是按索引保存，
    因为 PortAudio 索引在重启/拔插后会漂移。
    """
    if configured is None or str(configured).strip() == "":
        return None
    if isinstance(configured, int):
        return configured
    text = str(configured).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    try:
        import sounddevice as sd
    except ImportError:
        return None

    matches = [d for d in input_devices() if text.lower() in d["name"].lower()]
    if not matches:
        logger.warning(
            "Configured input device '%s' not found; using system default",
            configured,
        )
        return None
    if len(matches) == 1:
        return matches[0]["index"]
    # 多个同名设备（不同 host API）：取第一个能按 16k 单声道打开的
    for dev in matches:
        try:
            with sd.RawInputStream(
                samplerate=16000, blocksize=1600, dtype="int16",
                channels=1, device=dev["index"],
            ):
                return dev["index"]
        except Exception:
            continue
    return matches[0]["index"]


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

        # capture_channels：实际向声卡请求的声道数。
        # 显式指定设备且设备是多声道时，按设备声道采集再下混为单声道，
        # 避免「按单声道请求拿到静音」。默认设备仍按 1 声道保持旧行为。
        capture_channels = self._channels
        if self._device is not None and isinstance(self._device, int):
            try:
                info = sd.query_devices(self._device)
                if info is not None and int(info["max_input_channels"] or 1) > 1:
                    capture_channels = min(int(info["max_input_channels"]), 8)
            except Exception:
                logger.debug(
                    "Failed to query device %s channels", self._device,
                    exc_info=True,
                )

        try:
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=self._blocksize,
                dtype="int16",
                channels=capture_channels,
                device=self._device,
                latency=self._latency,
                callback=self._on_audio,
            )
            self._stream.start()
            self._running = True
            self._actual_sample_rate = self._stream.samplerate
            actual_channels = getattr(self._stream, "channels", capture_channels)
            self._actual_channels = actual_channels
            if self._actual_sample_rate != self._sample_rate:
                logger.warning(
                    "Audio capture actual sample rate %dHz differs from "
                    "requested %dHz",
                    self._actual_sample_rate,
                    self._sample_rate,
                )
            # Provider（SenseVoice/AssemblyAI）只吃单声道。多声道输入在这里
            # 自动下混为单声道，不再直接失败——否则「麦克风阵列」这类多声道
            # 设备一选就废，用户又无从得知原因。
            if actual_channels > 1:
                logger.info(
                    "Audio device reports %d channels; downmixing to mono",
                    actual_channels,
                )
            elif actual_channels != 1:
                logger.warning(
                    "Audio device reports %d channels; pipelines requires "
                    "mono, result may be invalid",
                    actual_channels,
                )
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

    def _on_audio(self, indata, frames, time_info, status):
        # 注：签名中参数不得修改
        if status:
            logger.warning("Audio status: %s", status)
        if self._callback:
            # 多声道交错 PCM 下混成单声道（16bit 内取平均），
            # 保证下游 RMS 分段与 ASR 只见到单声道数据。
            channels = self._actual_channels or 1
            try:
                if channels > 1:
                    raw = np.frombuffer(bytes(indata), dtype=np.int16)
                    usable = len(raw) - (len(raw) % channels)
                    mono = raw[:usable].reshape(-1, channels).astype(
                        np.int32
                    )
                    mono = np.mean(mono, axis=1).astype(np.int16)
                    data = bytes(mono.tobytes())
                else:
                    data = bytes(indata)
            except Exception:
                logger.exception("Error downmixing audio block")
                return
            try:
                self._callback(data)
            except Exception:
                logger.exception("Error in audio callback")
