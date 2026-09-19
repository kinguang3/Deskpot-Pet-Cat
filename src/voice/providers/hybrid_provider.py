# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""混合语音 Provider

同时调用两个子 Provider，让它们各司其职：

- AssemblyAI（云端）：高质量转录、英语情绪分析
- SenseVoice（本地 GGUF）：中文情绪分析、语种识别、音频事件检测

两个 Provider 通过 ThreadPoolExecutor 并行执行，再按语言与可用性
合并结果。任一 Provider 失败时自动降级到另一个，保证服务不中断。

合并规则：

============  ==================================================
字段           来源
============  ==================================================
text          优先 AssemblyAI，为空则用 SenseVoice
language      优先 SenseVoice，失败时退回 AssemblyAI
emotion       语言为 en 且 AssemblyAI 情绪有效时用其极性映射，
              否则用 SenseVoice 的原生情绪
confidence    与情绪来源对应
segments      与情绪来源对应
event         来自 SenseVoice
textnorm      来自 SenseVoice
raw           {"assemblyai": ..., "sensevoice": ...}
============  ==================================================
"""

import concurrent.futures
import threading

from src.utils.logger import get_logger
from src.voice.providers.base import BaseVoiceProvider

logger = get_logger(__name__)

#: AssemblyAI 情绪分析仅支持英语
_EN_LANGUAGE = "en"

#: 视为有效的 AssemblyAI 情绪极性
_VALID_SENTIMENTS = {"POSITIVE", "NEUTRAL", "NEGATIVE"}


class HybridVoiceProvider(BaseVoiceProvider):
    """并行调用 AssemblyAI 与 SenseVoice 并按语言合并结果"""

    name = "hybrid"

    def __init__(
        self,
        assemblyai_provider=None,
        sensevoice_provider=None,
        allow_partial: bool = False,
        max_workers: int = 2,
    ):
        """
        Args:
            assemblyai_provider: AssemblyAIProvider 实例，可为 None
            sensevoice_provider: SenseVoiceGGUFProvider 实例，可为 None
            allow_partial: 允许只有单个子 Provider 就绪时继续工作
            max_workers: 并行推理线程数上限
        """
        self._assemblyai = assemblyai_provider
        self._sensevoice = sensevoice_provider
        self._allow_partial = bool(allow_partial)
        self._max_workers = max(1, int(max_workers))

        self._executor = None
        self._executor_lock = threading.Lock()

        self._warn_not_ready()

    # BaseVoiceProvider 接口

    def is_ready(self) -> bool:
        """两个子 Provider 都就绪才返回 True；允许降级时任一就绪即可"""
        states = [
            provider.is_ready()
            for provider in (self._assemblyai, self._sensevoice)
            if provider is not None
        ]
        if not states:
            return False
        if self._allow_partial:
            return any(states)
        return all(states)

    def transcribe_and_analyze(self, audio_bytes: bytes) -> dict:
        """并行调用两个 Provider，合并成一个统一结构"""
        if not audio_bytes:
            return self._empty_result()
        if not self.is_ready():
            logger.error("HybridVoiceProvider not ready, returning empty")
            return self._empty_result()

        assemblyai_result, sensevoice_result = self._run_in_parallel(
            audio_bytes
        )
        return self._merge(assemblyai_result, sensevoice_result)

    def close(self) -> None:
        """关闭线程池并释放两个子 Provider"""
        with self._executor_lock:
            if self._executor is not None:
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None

        for provider in (self._assemblyai, self._sensevoice):
            if provider is None:
                continue
            try:
                provider.close()
            except Exception:
                logger.exception(
                    "Failed to close %s provider", provider.name
                )

    # 内部实现

    def _warn_not_ready(self):
        """启动时明确提示哪些子 Provider 未就绪"""
        missing = []
        if self._assemblyai is None:
            missing.append("assemblyai(未配置)")
        elif not self._assemblyai.is_ready():
            missing.append("assemblyai(配置或依赖缺失)")
        if self._sensevoice is None:
            missing.append("sensevoice(未配置)")
        elif not self._sensevoice.is_ready():
            missing.append("sensevoice(模型或可执行文件缺失)")

        if not missing:
            return
        if self._allow_partial:
            logger.warning(
                "HybridVoiceProvider 部分降级：%s 未就绪，将仅使用可用的"
                " Provider",
                ", ".join(missing),
            )
        else:
            logger.warning(
                "HybridVoiceProvider 无法工作：%s 未就绪（可配置 "
                "voice.hybrid.allow_partial_provider 允许降级）",
                ", ".join(missing),
            )

    def _ensure_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        with self._executor_lock:
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self._max_workers,
                    thread_name_prefix="HybridVoice",
                )
            return self._executor

    def _run_in_parallel(self, audio_bytes: bytes):
        """并行执行两个 Provider，返回 (assemblyai_result, sensevoice_result)"""
        targets = []
        if self._assemblyai is not None and self._assemblyai.is_ready():
            targets.append(("assemblyai", self._assemblyai))
        if self._sensevoice is not None and self._sensevoice.is_ready():
            targets.append(("sensevoice", self._sensevoice))

        if not targets:
            logger.error("HybridVoiceProvider 没有可用的子 Provider")
            return None, None

        results = {}
        executor = self._ensure_executor()
        future_map = {
            executor.submit(
                provider.transcribe_and_analyze, audio_bytes
            ): name
            for name, provider in targets
        }
        for future in concurrent.futures.as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception:
                logger.warning(
                    "Hybrid %s provider 调用失败，降级到另一个 Provider",
                    name,
                    exc_info=True,
                )
                results[name] = None

        assemblyai_result = results.get("assemblyai")
        sensevoice_result = results.get("sensevoice")
        if assemblyai_result is None and sensevoice_result is None:
            logger.error("Hybrid 两个 Provider 均失败，返回空结果")
        return assemblyai_result, sensevoice_result

    def _merge(self, assemblyai_result: dict, sensevoice_result: dict) -> dict:
        """按语言与可用性合并两个 Provider 的结果"""
        assemblyai_result = assemblyai_result or {}
        sensevoice_result = sensevoice_result or {}

        # 文本：优先 AssemblyAI 的高质量转录
        text = (assemblyai_result.get("text") or "").strip()
        if not text:
            text = (sensevoice_result.get("text") or "").strip()

        # 语言：优先 SenseVoice 的语种识别，失败时退回 AssemblyAI
        language = self._pick_language(
            assemblyai_result, sensevoice_result
        )

        # 情绪：英语且 AssemblyAI 情绪有效时用 AssemblyAI，否则用 SenseVoice
        if self._is_assemblyai_emotion_valid(assemblyai_result, language):
            sentiment = (
                assemblyai_result.get("sentiment") or "NEUTRAL"
            ).upper()
            confidence = float(assemblyai_result.get("confidence") or 0.0)
            segments = list(assemblyai_result.get("segments") or [])
            # AssemblyAI 只给极性，具体情绪留给 EmotionParser 映射
            emotion = ""
            emotion_source = "assemblyai"
        else:
            sentiment = (
                sensevoice_result.get("sentiment") or "UNKNOWN"
            ).upper()
            confidence = float(sensevoice_result.get("confidence") or 0.0)
            segments = list(sensevoice_result.get("segments") or [])
            emotion = (sensevoice_result.get("emotion") or "UNKNOWN").upper()
            emotion_source = "sensevoice"

        logger.debug(
            "Hybrid merged result: lang=%s emotion_source=%s text=%r",
            language,
            emotion_source,
            text,
        )

        return {
            "text": text,
            "emotion": emotion,
            "sentiment": sentiment,
            "confidence": confidence,
            "segments": segments,
            "language": language,
            "event": sensevoice_result.get("event", "UNKNOWN"),
            "textnorm": sensevoice_result.get("textnorm", "UNKNOWN"),
            "emotion_source": emotion_source,
            "raw": {
                "assemblyai": assemblyai_result.get("raw", {}),
                "sensevoice": sensevoice_result.get("raw", {}),
            },
        }

    def _pick_language(self, assemblyai_result: dict, sensevoice_result: dict):
        """语言优先取 SenseVoice，缺失时退回 AssemblyAI"""
        sensevoice_language = (
            sensevoice_result.get("language") or ""
        ).upper()
        if sensevoice_language and sensevoice_language != "UNKNOWN":
            return sensevoice_language

        assemblyai_language = (
            assemblyai_result.get("language") or ""
        ).upper()
        if assemblyai_language:
            return assemblyai_language
        return "UNKNOWN"

    def _is_assemblyai_emotion_valid(
        self, assemblyai_result: dict, language: str
    ) -> bool:
        """仅当语言为英语且 AssemblyAI 给出了有效的极性情绪时才采用"""
        if language.lower() != _EN_LANGUAGE:
            return False
        sentiment = (assemblyai_result.get("sentiment") or "").upper()
        if sentiment not in _VALID_SENTIMENTS:
            return False
        confidence = float(assemblyai_result.get("confidence") or 0.0)
        if confidence <= 0.0 and not assemblyai_result.get("segments"):
            return False
        return True

    @staticmethod
    def _empty_result() -> dict:
        return {
            "text": "",
            "emotion": "UNKNOWN",
            "sentiment": "UNKNOWN",
            "confidence": 0.0,
            "segments": [],
            "language": "UNKNOWN",
            "event": "UNKNOWN",
            "textnorm": "UNKNOWN",
            "emotion_source": "unknown",
            "raw": {},
        }
