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
DEFAULT_WAKE_PHRASE = "嘿"

# 可接受的唤醒词变体（用于匹配）
# Vosk 中文模型可能输出同音字
WAKE_VARIANTS = [
    "嘿",
    "黑",
    "嗨",
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
        self._command_callback = None
        self._thread: threading.Thread = None
        self._audio_queue: queue.Queue = queue.Queue()

        # Vosk 组件
        self._model = None
        self._recognizer = None
        self._stream = None

        # 冷却时间
        self._cooldown = 2.0  # 秒
        self._last_trigger_time = 0

        # 命令窗口模式
        self._command_mode = False

        # 始终命令模式（非 sleep 时所有语音都当命令处理）
        self._always_command = False

        logger.debug("WakeDetector initialized (phrase: %s)", wake_phrase)

    def set_callback(self, callback):
        """设置唤醒回调函数。"""
        self._callback = callback

    def set_command_callback(self, callback):
        """设置命令回调函数（命令窗口内所有语音文本）。"""
        self._command_callback = callback

    def enter_command_mode(self):
        """进入命令窗口模式（唤醒后接收语音命令）。"""
        self._command_mode = True
        logger.info("[Voice] Command mode ON")

    def exit_command_mode(self):
        """退出命令窗口模式。"""
        self._command_mode = False
        logger.info("[Voice] Command mode OFF")

    def set_always_command(self, enabled: bool):
        """设置始终命令模式。

        开启后，所有识别文本同时发送给命令回调。
        唤醒词仍然触发唤醒回调。
        用于非 sleep 状态下直接执行语音命令。
        """
        self._always_command = enabled
        logger.info("[Voice] Always-command mode: %s", enabled)

    def start(self) -> bool:
        """启动唤醒检测。

        Returns:
            是否成功启动
        """
        if self._running:
            return True

        # 检查权限，首次时请求权限
        if not self._check_microphone_permission():
            # 无权限立即停止
            return False

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
        """加载 Vosk 模型，不存在时自动下载。"""
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
                if not self._download_model(model_dir):
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

    def _check_microphone_permission(self) -> bool:
        """检查录音权限"""
        try:
            import sounddevice as sd

            sd.check_input_settings(device=None, channels=1, samplerate=16000)
            return True
        except sd.PortAudioError as e:
            logger.error(
                "Microphone permission denied or no input device: %s", e
            )
            return False
        except Exception as e:
            logger.error("Microphone check failed: %s", e)
            return False

    def _download_model(self, model_dir: Path) -> bool:
        """下载 Vosk 中文模型。"""
        import urllib.request
        import zipfile
        import tempfile

        url = (
            "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
        )
        zip_name = "vosk-model-small-cn-0.22.zip"

        logger.info("Downloading Vosk model from %s ...", url)
        logger.info("This is a one-time download (~44MB).")

        try:
            # 创建 models 目录
            models_parent = model_dir.parent
            models_parent.mkdir(parents=True, exist_ok=True)

            # 下载到临时文件
            with tempfile.TemporaryDirectory() as tmp_dir:
                zip_path = Path(tmp_dir) / zip_name

                def _progress(block_num, block_size, total_size):
                    downloaded = block_num * block_size
                    if total_size > 0:
                        pct = min(100, downloaded * 100 // total_size)
                        if pct % 10 == 0:
                            logger.info("Downloading model: %d%%", pct)

                urllib.request.urlretrieve(url, str(zip_path), _progress)

                # 解压
                logger.info("Extracting model...")
                with zipfile.ZipFile(str(zip_path), "r") as zf:
                    zf.extractall(str(models_parent))

            logger.info("Model downloaded to: %s", model_dir)
            return True

        except Exception:
            logger.exception("Failed to download Vosk model")
            logger.error("Please download manually from: %s", url)
            logger.error("Extract to: %s", models_parent)
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
                        logger.info("[Voice Recognized] %s", text)
                        print("[Voice] " + text)
                        self._dispatch_text(text)

                # 也检查部分结果
                partial = json.loads(self._recognizer.PartialResult())
                partial_text = partial.get("partial", "").lower()
                if partial_text:
                    logger.debug("[Voice Partial] %s", partial_text)
                    print("[Voice] ... " + partial_text)
                    # 命令模式或始终命令模式下转发部分结果
                    if self._command_mode or self._always_command:
                        if self._command_callback:
                            try:
                                self._command_callback(partial_text)
                            except Exception:
                                logger.exception("Error in command callback")

            except Exception:
                if self._running:
                    logger.exception("Error in listen loop")

        logger.debug("Listening loop ended")

    def _dispatch_text(self, text: str):
        """分发识别文本。"""
        # 始终检查唤醒词（任何状态下说「嘿」都能唤醒）
        self._check_wake_word(text)

        # 始终命令模式：所有文本同时发给命令回调
        if self._always_command and self._command_callback:
            try:
                self._command_callback(text)
            except Exception:
                logger.exception("Error in command callback")
        # 普通命令窗口模式：只在命令窗口期内发给命令回调
        elif self._command_mode and self._command_callback:
            try:
                self._command_callback(text)
            except Exception:
                logger.exception("Error in command callback")

    def _check_wake_word(self, text: str):
        """检查文本中是否包含唤醒词。"""
        # 冷却检查
        now = time.time()
        if now - self._last_trigger_time < self._cooldown:
            remaining = self._cooldown - (now - self._last_trigger_time)
            logger.debug("[Voice] Cooldown: %.1fs remaining", remaining)
            return

        # 检查是否匹配唤醒词
        for variant in WAKE_VARIANTS:
            if variant in text:
                self._last_trigger_time = now
                logger.info("[Voice] WAKE DETECTED: %s", text)
                print("[Voice] *** WAKE DETECTED: " + text + " ***")

                if self._callback:
                    try:
                        self._callback(text)
                    except Exception:
                        logger.exception("Error in wake callback")
                break

    @property
    def is_running(self) -> bool:
        return self._running

    @classmethod
    def has_microphone(cls) -> bool:
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            for dev in devices:
                if dev['max_input_channels'] > 0:
                    return True
            return False
        except Exception as e:
            logger.error("Microphone query failed: %s", e)
            return False
