# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""SenseVoiceSmall GGUF 本地推理 Provider

通过 subprocess 调用 llama-funasr-sensevoice 可执行文件
对 PCM 音频做转录 + 情绪分析 + 语种识别 + 音频事件检测

工作流程：
1. 把 16kHz/16bit/单声道 PCM 字节写入临时 WAV 文件；
2. 调用 llama-funasr-sensevoice.exe，指定模型、VAD、音频路径，
   并传入 --keep-tags 以保留语言/情绪/事件标签；
3. 解析富文本输出（如 <|zh|><|HAPPY|><|Speech|><|withitn|>文本）；
4. 返回 BaseVoiceProvider 约定的统一结构

输出标签说明（4 个前置标签，顺序固定）：
    <|语言|><|情绪|><|事件|><|文本规范化|>转录文本

语言: zh / en / yue / ja / ko / nospeech
情绪: HAPPY / SAD / ANGRY / NEUTRAL / EMO_UNKNOWN
事件: Speech / Music / Applause / Laughter / Cry / BGM
规范化: withitn（含数字与标点）/ woitn（原始）
"""

import os
import re
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from src.core.config import ConfigManager
from src.utils.logger import get_logger
from src.voice.providers.base import BaseVoiceProvider

logger = get_logger(__name__)


# 匹配 4 个前置富文本标签
_TAG_PATTERN = re.compile(r"<\|(.*?)\|>")

# 情绪标签集合（用于校验解析结果是否合理）
_KNOWN_EMOTIONS = {
    "HAPPY",
    "SAD",
    "ANGRY",
    "NEUTRAL",
    "EMO_UNKNOWN",
    "FEARFUL",
    "DISGUSTED",
    "SURPRISED",
}


class SenseVoiceGGUFProvider(BaseVoiceProvider):
    """基于 llama-funasr-sensevoice 二进制的本地语音情绪识别 Provider"""

    name = "sensevoice"

    def __init__(
        self,
        exe_path,
        model_path,
        vad_path,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        timeout: float = 30.0,
        n_threads: int = 8,
        thread_flag: str = None,
    ):
        """
        Args:
            exe_path: llama-funasr-sensevoice.exe 的绝对路径
            model_path: sensevoice-small-q8.gguf 的绝对路径
            vad_path: fsmn-vad.gguf 的绝对路径
            sample_rate: 音频采样率，SenseVoice 要求 16000
            channels: 声道数，要求单声道
            sample_width: 每个采样点字节数，int16 为 2
            timeout: 单次推理超时秒数
            n_threads: CPU 推理线程数
            thread_flag: 线程数命令行参数；None 表示自动探测，
                空字符串表示不透传（二进制不支持时使用）
        """
        self._exe_path = Path(exe_path) if exe_path else None
        self._model_path = Path(model_path) if model_path else None
        self._vad_path = Path(vad_path) if vad_path else None

        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_width = sample_width
        self._timeout = timeout
        self._n_threads = n_threads
        self._thread_flag = thread_flag
        self._resolved_thread_flag = None
        self._thread_flag_lock = threading.Lock()

        self._config = ConfigManager()
        self._language = self._config.get("voice.sensevoice.language", "zh")

        self._ready = self._check_ready()
        if self._ready:
            logger.info(
                "SenseVoiceGGUFProvider ready (model=%s)",
                self._model_path.name,
            )
        else:
            logger.error("SenseVoiceGGUFProvider not ready, check paths")

        configured = self._config.get_path("voice.sensevoice.temp_path")
        self._temp_dir = (
            Path(configured) if configured else Path(tempfile.gettempdir())
        )
        try:
            self._temp_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception(
                "Failed to create temp dir, fallback to system temp"
            )
            self._temp_dir = Path(tempfile.gettempdir())
            self._temp_dir.mkdir(parents=True, exist_ok=True)

    # BaseVoiceProvider 接口

    def is_ready(self) -> bool:
        return self._ready

    def transcribe_and_analyze(self, audio_bytes: bytes) -> dict:
        """对一段 PCM 音频做转录与情绪分析

        Args:
            audio_bytes: 16kHz / 16bit / 单声道 PCM 原始字节

        Returns:
            统一结构 dict，字段含义见 BaseVoiceProvider
        """
        if not self._ready:
            logger.error("Provider not ready, returning empty result")
            return self._empty_result()

        if not audio_bytes:
            return self._empty_result()

        wav_path = None
        try:
            wav_path = self._pcm_to_wav(audio_bytes)
            raw_output, stderr = self._run_inference(wav_path)
            parsed = self._parse_output(raw_output)

            # stderr 一并带回，便于排查二进制运行问题
            parsed["raw"] = {
                "stdout": raw_output,
                "stderr": stderr,
            }
            if stderr:
                logger.debug("SenseVoice stderr: %s", stderr)
            return parsed

        except subprocess.TimeoutExpired:
            logger.error(
                "SenseVoice inference timed out after %.1fs", self._timeout
            )
            return self._empty_result()
        except Exception:
            logger.exception("SenseVoice inference failed")
            return self._empty_result()
        finally:
            self._remove_temp_wav(wav_path)

    def close(self) -> None:
        """无需释放的持久资源，保持接口兼容"""
        return None

    # 内部实现

    def _check_ready(self) -> bool:
        """校验三个关键文件是否存在，缺失时一次性列出全部问题"""
        checks = [
            ("可执行文件", self._exe_path),
            ("模型文件", self._model_path),
            ("VAD 模型", self._vad_path),
        ]
        missing = [
            f"{label}: {path}"
            for label, path in checks
            if not path or not path.is_file()
        ]
        if missing:
            logger.error(
                "SenseVoiceGGUFProvider 缺少以下文件，无法启动：\n- %s",
                "\n- ".join(missing),
            )
            return False
        return True

    def _pcm_to_wav(self, pcm_bytes: bytes) -> str:
        """把 PCM 字节写成临时 WAV 文件，返回文件路径"""
        fd, wav_path = tempfile.mkstemp(
            suffix=".wav", prefix="sv_", dir=str(self._temp_dir)
        )
        try:
            with os.fdopen(fd, "wb") as f:
                # 句柄已交给 fdopen 管理
                fd = -1
                with wave.open(f, "wb") as wf:
                    wf.setnchannels(self._channels)
                    wf.setsampwidth(self._sample_width)
                    wf.setframerate(self._sample_rate)
                    wf.writeframes(pcm_bytes)
        except Exception:
            # 写失败也要关闭句柄并清理临时文件
            if fd != -1:
                try:
                    os.close(fd)
                except OSError:
                    pass
            self._remove_temp_wav(wav_path)
            raise
        return wav_path

    def _run_inference(self, wav_path: str):
        """调用二进制程序，返回 (stdout 文本, stderr 文本)"""
        cmd = [
            str(self._exe_path),
            "-m",
            str(self._model_path),
            "--vad",
            str(self._vad_path),
            "-l",
            str(self._language),
            "-a",
            wav_path,
            "--keep-tags",  # 保留语言/情绪/事件标签
        ]

        # 按二进制实际支持的参数透传线程数
        thread_flag = self._resolve_thread_flag()
        if thread_flag:
            cmd.extend([thread_flag, str(self._n_threads)])

        logger.debug("Running SenseVoice: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self._timeout,
            check=False,  # 非零退出码也先拿输出，由解析层判断
        )

        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            logger.error(
                "SenseVoice exited with code %d: %s",
                result.returncode,
                stderr,
            )
            return "", stderr

        return (result.stdout or "").strip(), stderr

    def _resolve_thread_flag(self) -> str:
        """返回可用的线程数参数，无则返回空字符串"""
        with self._thread_flag_lock:
            if self._resolved_thread_flag is not None:
                return self._resolved_thread_flag
            if self._thread_flag is not None:
                self._resolved_thread_flag = self._thread_flag
            else:
                self._resolved_thread_flag = self._detect_thread_flag()
            return self._resolved_thread_flag

    def _detect_thread_flag(self) -> str:
        """通过 --help 探测二进制支持的线程数参数名

        llama-funasr-sensevoice 不同版本参数名不同（-t / --threads），
        探测失败时直接不透传，保证推理仍可正常执行。
        """
        if not self._exe_path or not self._exe_path.is_file():
            return ""
        try:
            result = subprocess.run(
                [str(self._exe_path), "--help"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5.0,
                check=False,
            )
        except Exception:
            logger.debug(
                "SenseVoice thread flag probing failed", exc_info=True
            )
            return ""

        help_text = (result.stdout or "") + (result.stderr or "")
        for flag in ("--threads", "-t"):
            pattern = r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])"
            if re.search(pattern, help_text):
                logger.info("SenseVoice binary supports thread flag: %s", flag)
                return flag

        logger.info(
            "SenseVoice binary declares no thread flag, skip n_threads"
        )
        return ""

    def _remove_temp_wav(self, wav_path):
        """删除临时 WAV，忽略文件不存在等错误"""
        if not wav_path:
            return
        try:
            Path(wav_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove temp wav: %s", wav_path)

    def _parse_output(self, raw_text: str) -> dict:
        """解析富文本输出，提取语言、情绪、事件、规范化与纯文本"""
        if not raw_text:
            return self._empty_result()

        # 标签按出现顺序提取
        tags = _TAG_PATTERN.findall(raw_text)
        clean_text = _TAG_PATTERN.sub("", raw_text).strip()

        language = "UNKNOWN"
        emotion = "UNKNOWN"
        event = "UNKNOWN"
        textnorm = "UNKNOWN"

        # 标准输出为 4 个前置标签：lang, emotion, event, textnorm
        if len(tags) >= 4:
            language = tags[0].upper()
            emotion = tags[1].upper()
            event = tags[2]
            textnorm = tags[3].lower()
        elif len(tags) >= 1:
            # 容错：至少尝试识别情绪标签
            for tag in tags:
                t = tag.upper()
                if t in _KNOWN_EMOTIONS:
                    emotion = t
                    break

        # 情绪标签兜底校验
        if emotion not in _KNOWN_EMOTIONS:
            emotion = "EMO_UNKNOWN"

        # SenseVoice 直接输出具体情绪，不输出极性
        # 这里映射为基类约定的 POSITIVE/NEUTRAL/NEGATIVE 极性
        # 供 EmotionParser 做二次归一化
        sentiment = self._emotion_to_sentiment(emotion)

        return {
            "text": clean_text,
            "sentiment": sentiment,
            "emotion": emotion,  # 原生情绪标签，供 EmotionParser 直接使用
            "language": language,
            "event": event,
            "textnorm": textnorm,
            "confidence": 1.0,  # SenseVoice 不提供置信度，视为完全可信
            "segments": [],  # 单次调用对应一段完整音频，无逐句切分
        }

    @staticmethod
    def _emotion_to_sentiment(emotion: str) -> str:
        """把 SenseVoice 原生情绪映射为极性"""
        if emotion == "HAPPY":
            return "POSITIVE"
        if emotion in ("SAD", "ANGRY", "FEARFUL", "DISGUSTED"):
            return "NEGATIVE"
        if emotion == "NEUTRAL":
            return "NEUTRAL"
        return "UNKNOWN"

    @staticmethod
    def _empty_result() -> dict:
        return {
            "text": "",
            "sentiment": "UNKNOWN",
            "emotion": "UNKNOWN",
            "language": "UNKNOWN",
            "event": "UNKNOWN",
            "textnorm": "UNKNOWN",
            "confidence": 0.0,
            "segments": [],
            "raw": {},
        }
