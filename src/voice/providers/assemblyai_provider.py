# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""AssemblyAI 提供方实现

注意：
- AssemblyAI 的情绪分析仅支持英语
- 音频以 WAV 临时文件方式上传，简单可靠
- API Key 从 ConfigManager 或环境变量读取
"""

import os
import struct
import tempfile
import wave
from pathlib import Path

from src.utils.logger import get_logger
from src.voice.providers.base import BaseVoiceProvider

logger = get_logger(__name__)


class AssemblyAIProvider(BaseVoiceProvider):
    """基于 AssemblyAI 的转录 + 情绪分析"""

    name = "assemblyai"

    def __init__(
        self,
        api_key: str = None,
        language: str = "en",
        sample_rate: int = 16000,
        channels: int = 1,
        timeout: int = 60,
    ):
        self._api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY", "")
        self._language = language
        self._sample_rate = sample_rate
        self._channels = channels
        self._timeout = timeout
        self._client = None

        if not self._api_key:
            logger.warning("AssemblyAI API key is empty")

    def is_ready(self) -> bool:
        if not self._api_key:
            return False
        try:
            import assemblyai  # noqa: F401
        except ImportError:
            logger.error(
                "assemblyai not installed. Run: pip install assemblyai"
            )
            return False
        return True

    def _ensure_client(self):
        if self._client is not None:
            return
        import assemblyai as aai

        aai.settings.api_key = self._api_key
        aai.settings.http_timeout = self._timeout
        self._client = aai

    def transcribe_and_analyze(self, audio_bytes: bytes) -> dict:
        empty = {
            "text": "",
            "sentiment": "UNKNOWN",
            "confidence": 0.0,
            "segments": [],
            "raw": {},
        }
        if not audio_bytes:
            return empty
        if not self.is_ready():
            return empty

        self._ensure_client()
        aai = self._client

        # 写临时 WAV
        tmp_path = self._write_wav(audio_bytes)
        if tmp_path is None:
            return empty

        try:
            config = aai.TranscriptionConfig(
                sentiment_analysis=True,
                language_code=self._language,
            )
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(str(tmp_path), config=config)

            if transcript.status == aai.TranscriptStatus.error:
                logger.error(
                    "AssemblyAI transcription failed: %s", transcript.error
                )
                return empty

            return self._normalize(transcript)
        except Exception:
            logger.exception("AssemblyAI request failed")
            return empty
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _write_wav(self, audio_bytes: bytes) -> str:
        """把 PCM bytes 写成临时 WAV 文件"""
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="voice_"
            )
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(self._channels)
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(self._sample_rate)
                wf.writeframes(audio_bytes)
            return tmp.name
        except Exception:
            logger.exception("Failed to write temp wav")
            return None

    def _normalize(self, transcript) -> dict:
        """把 AssemblyAI 的返回整理成统一结构"""
        segments = []
        confidences = []

        for item in transcript.sentiment_analysis_results or []:
            seg = {
                "text": item.text or "",
                "sentiment": (item.sentiment or "NEUTRAL").upper(),
                "confidence": float(item.confidence or 0.0),
                "start_ms": int(item.start or 0),
                "end_ms": int(item.end or 0),
            }
            segments.append(seg)
            confidences.append(seg["confidence"])

        if segments:
            # 取置信度最高的一句作为整体情感
            best = max(segments, key=lambda s: s["confidence"])
            overall_sentiment = best["sentiment"]
            overall_conf = best["confidence"]
        else:
            overall_sentiment = "NEUTRAL"
            overall_conf = 0.0

        return {
            "text": transcript.text or "",
            "sentiment": overall_sentiment,
            "confidence": overall_conf,
            "segments": segments,
            "raw": {"id": getattr(transcript, "id", None)},
        }
