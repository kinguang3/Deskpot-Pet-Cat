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
            sentiment = self._language == "en"
            config = aai.TranscriptionConfig(
                sentiment_analysis=sentiment,
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
            self._remove_temp_file(tmp_path)

    def _write_wav(self, audio_bytes: bytes) -> str:
        """把 PCM bytes 写成临时 WAV 文件，失败时清理残留文件"""
        tmp_path = None
        success = False
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="voice_"
            )
            tmp_path = tmp.name
            # 先关闭 mkstemp 句柄，避免 Windows 上重复打开失败
            tmp.close()
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(self._channels)
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(self._sample_rate)
                wf.writeframes(audio_bytes)
            success = True
            return tmp_path
        except Exception:
            logger.exception("Failed to write temp wav")
            return None
        finally:
            if not success:
                self._remove_temp_file(tmp_path)

    @staticmethod
    def _remove_temp_file(tmp_path):
        """删除临时文件，忽略文件不存在等错误"""
        if not tmp_path:
            return
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove temp file: %s", tmp_path)

    def _normalize(self, transcript) -> dict:
        """把 AssemblyAI 的返回整理成统一结构"""
        segments = []

        results = getattr(transcript, "sentiment_analysis_results", None) or []
        for item in results:
            seg = {
                "text": item.text or "",
                "sentiment": (item.sentiment or "NEUTRAL").upper(),
                "confidence": float(item.confidence or 0.0),
                "start_ms": int(item.start or 0),
                "end_ms": int(item.end or 0),
            }
            segments.append(seg)

        if segments:
            overall_sentiment, overall_conf = self._aggregate(segments)
        else:
            overall_sentiment = "NEUTRAL"
            overall_conf = 0.0

        return {
            "text": transcript.text or "",
            "sentiment": overall_sentiment,
            "confidence": overall_conf,
            # 透传配置语种，供 HybridVoiceProvider 合并时兜底
            "language": self._language,
            "segments": segments,
            "raw": {"id": getattr(transcript, "id", None)},
        }

    @staticmethod
    def _aggregate(segments: list):
        """按文本长度加权投票聚合整体情绪

        - 票权 = 句子文本长度（空文本按 1 计），避免短句主导整体结果
        - 整体置信度 = 该情绪下按票权加权的平均置信度
        """
        weights = {}
        weighted_conf = {}
        for seg in segments:
            sentiment = seg.get("sentiment") or "NEUTRAL"
            weight = max(len(seg.get("text") or ""), 1)
            weights[sentiment] = weights.get(sentiment, 0) + weight
            weighted_conf[sentiment] = weighted_conf.get(
                sentiment, 0.0
            ) + float(seg.get("confidence") or 0.0) * weight

        if not weights:
            return "NEUTRAL", 0.0

        overall_sentiment = max(weights, key=weights.get)
        overall_conf = (
            weighted_conf[overall_sentiment] / weights[overall_sentiment]
        )
        return overall_sentiment, overall_conf
