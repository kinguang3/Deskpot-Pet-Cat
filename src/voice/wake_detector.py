# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""唤醒词检测模块

使用 Vosk 进行离线语音识别，检测「嘿，Nina」唤醒词。
"""

import json
import queue
import time
import threading
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 默认唤醒词
DEFAULT_WAKE_PHRASE = "嘿nina"

# 可接受的唤醒词变体（用于匹配）
WAKE_VARIANTS = [
    "嘿nina",
    "嘿 妮娜",
    "嘿妮娜",
    "嘿nina",
    "hey nina",
    "heynina",
]


class WakeDetector:
    """唤醒词检测器。

    使用 Vosk 进行离线语音识别。
    在后台线程中运行，检测到唤醒词时通过回调通知。
    """

    def __init__(
        self,
        model_path: str = None,
        wake_phrase: str = DEFAULT_WAKE_PHRASE,
    ):
        self._model_path = model_path
        self._wake_phrase = wake_phrase.lower()
        self._running = False
        self._callback = None
        self._thread: threading.Thread = None
        self._audio_queue: queue.Queue = queue.Queue()

        # Vosk 组件
        self._model = None
        self._recognizer = None
        self._stream = None

        # 冷却时间
        self._cooldown = 2.0  # 秒
        self._last_trigger_time = 0

        logger.debug("WakeDetector initialized (phrase: %s)", wake_phrase)

    def set_callback(self, callback):
        """设置唤醒回调函数。"""
        self._callback = callback

    def start(self) -> bool:
        """启动唤醒检测。

        Returns:
            是否成功启动
        """
        if self._running:
            return True

        # 加载模型
        if not self._load_model():
            return False

        # 启动音频流
        if not self._start_audio_stream():
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="VoiceWake"
        )
        self._thread.start()
        logger.info("Wake detection started")
        return True

    def stop(self):
        """停止唤醒检测。"""
        self._running = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        logger.info("Wake detection stopped")

    def _load_model(self) -> bool:
        """加载 Vosk 模型。"""
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel

            SetLogLevel(-1)  # 关闭 Vosk 日志

            # 查找模型路径
            if self._model_path is None:
                base_dir = Path(__file__).resolve().parent.parent.parent
                self._model_path = str(
                    base_dir / "models" / "vosk-model-small-cn-0.22"
                )

            model_dir = Path(self._model_path)
            if not model_dir.exists():
                logger.error("Vosk model not found: %s", self._model_path)
                return False

            self._model = Model(str(model_dir))
            self._recognizer = KaldiRecognizer(self._model, 16000)
            logger.info("Vosk model loaded: %s", model_dir.name)
            return True

        except ImportError:
            logger.error("Vosk not installed. Run: pip install vosk")
            return False
        except Exception:
            logger.exception("Failed to load Vosk model")
            return False

    def _start_audio_stream(self) -> bool:
        """启动音频流。"""
        try:
            import sounddevice as sd

            self._sd = sd
            self._stream = sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info("Microphone ready")
            return True

        except Exception:
            logger.exception("Failed to initialize microphone")
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        """音频回调（在音频线程中运行）。"""
        if status:
            logger.warning("Audio status: %s", status)
        self._audio_queue.put(bytes(indata))

    def _listen_loop(self):
        """监听循环（在后台线程中运行）。"""
        logger.debug("Listening loop started")

        while self._running:
            try:
                # 从队列获取音频数据（超时 0.5 秒）
                try:
                    data = self._audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # 送入识别器
                if self._recognizer.AcceptWaveform(data):
                    result = json.loads(self._recognizer.Result())
                    text = result.get("text", "").lower()
                    if text:
                        self._check_wake_word(text)

                # 也检查部分结果
                partial = json.loads(self._recognizer.PartialResult())
                partial_text = partial.get("partial", "").lower()
                if partial_text:
                    self._check_wake_word(partial_text)

            except Exception:
                if self._running:
                    logger.exception("Error in listen loop")

        logger.debug("Listening loop ended")

    def _check_wake_word(self, text: str):
        """检查文本中是否包含唤醒词。"""
        # 冷却检查
        now = time.time()
        if now - self._last_trigger_time < self._cooldown:
            return

        # 检查是否匹配唤醒词
        for variant in WAKE_VARIANTS:
            if variant in text:
                self._last_trigger_time = now
                logger.info("Wake phrase detected: %s", text)

                if self._callback:
                    try:
                        self._callback(text)
                    except Exception:
                        logger.exception("Error in wake callback")
                break

    @property
    def is_running(self) -> bool:
        return self._running
