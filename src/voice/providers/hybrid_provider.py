# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""混合语音 Provider

同时调用两个子 Provider，让它们各司其职：

- AssemblyAI（云端）：高质量转录、英语情绪分析
- SenseVoice（本地 GGUF）：中文情绪分析、语种识别、音频事件检测

两个 Provider **串行**配合，按语言与可用性合并结果。任一 Provider 失败时
自动降级到另一个，保证服务不中断。

延迟策略（命令场景优先响应）：
- SenseVoice 为本地推理，先行执行，通常远快于云端；中文场景下它的
  结果即为最终结果，**完全不调用** AssemblyAI，因此没有额外网络等待。
- 只有 SenseVoice 不可用、异常，或它把音频判为英文（非中文）时，才
  继续调用 AssemblyAI 兜底，保证英文转录与云端情绪能力不丢。

为什么不并行：
- 早期实现对两个 Provider 同时投递任务，且本地任务「完成即返回」。
  但线程池 worker 有限（默认 2），连续的语音段会先塞满 worker：
  本地推理很快（约 0.1s）但云端任务要跑 5~10s，占着 worker 不放，
  导致后续**本地**任务被排在云端任务后面，实测单段延迟被放大到
  2.8s（本地只需 0.1s）。
- 中文为主的场景根本用不到云端，投机并发只带来排队与资源浪费。
  改为「先本地、按需云端」后，同场景实测稳定在 0.1s。

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
        """先本地后云端地合并结果"""
        if not audio_bytes:
            return self._empty_result()

        # 注意：这里不能直接用 is_ready() 一刀切返回空结果。is_ready() 要求
        # 两个子 Provider 全部就绪，而本类的存在意义就是「一个挂了另一个
        # 顶上」。曾经写成 `if not self.is_ready(): return empty`，导致
        # SenseVoice 临时不可用（如 exe 被占用/被清理）时，AssemblyAI 明明
        # 完全可用却也被一起放弃，整条语音链路静默返回空结果。
        local_ready = self._provider_ready(self._sensevoice)
        cloud_ready = self._provider_ready(self._assemblyai)
        if not local_ready and not cloud_ready:
            logger.error(
                "HybridVoiceProvider not ready (both providers unavailable), "
                "returning empty"
            )
            return self._empty_result()

        return self._run_local_first(audio_bytes)

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
        problems = []
        for label, provider in (
            ("assemblyai", self._assemblyai),
            ("sensevoice", self._sensevoice),
        ):
            if provider is None:
                problems.append(f"{label}(未配置)")
            elif not provider.is_ready():
                problems.append(f"{label}(未就绪)")

        for problem in problems:
            logger.warning("HybridVoiceProvider 子 Provider %s", problem)

        if not problems:
            return
        if self._allow_partial:
            logger.warning(
                "HybridVoiceProvider 将降级为单 Provider 运行：%s",
                ", ".join(problems),
            )
        else:
            logger.warning(
                "HybridVoiceProvider 无法工作：%s（可配置 "
                "voice.hybrid.allow_partial_provider 允许降级）",
                ", ".join(problems),
            )

    def _ensure_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        with self._executor_lock:
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self._max_workers,
                    thread_name_prefix="HybridVoice",
                )
            return self._executor

    @staticmethod
    def _provider_ready(provider) -> bool:
        """就绪检查统一入口：子 Provider 的 is_ready() 自身抛异常时

        视为不可用而不是让异常冒泡打断整段识别。
        """
        if provider is None:
            return False
        try:
            return bool(provider.is_ready())
        except Exception:
            logger.warning(
                "Provider readiness check raised, treating as unavailable",
                exc_info=True,
            )
            return False

    def _run_local_first(self, audio_bytes: bytes) -> dict:
        """本地优先：SenseVoice 先跑，中文场景完全不调用云端

        设计重点（低延迟命令场景）：
        - SenseVoice 是本地推理（亚秒级），**先**执行并立即判断。
        - 若本地识别出中文/非英语文本，直接返回，**不调用** AssemblyAI：
          既避免云端 5~60s 延迟拖慢命令，也避免为中文语料白白消耗
          AssemblyAI 配额（早前版本云端 100% 被调用却从不参与中文结果
          合并）。
        - 若本地识别出英文，才补调 AssemblyAI 提升转写质量（此时延迟
          = 本地 + 云端，串行；英文场景可接受）。
        - 若本地不可用、崩溃或未识别出文本，则仅用 AssemblyAI 兜底。

        关键：云端任务**不再与本地并发提交**。早前版本用共享 2-worker
        线程池同时提交两者，慢速云端任务会占满 worker，使下一次本地推理
        被迫排队，出现「本地仅需 0.1s 却整体等待 2.8s」的延迟毛刺。
        """
        sensevoice_result = None
        if self._provider_ready(self._sensevoice):
            sensevoice_result = self._call_provider(
                self._sensevoice, audio_bytes, "SenseVoice 本地"
            )

        sensevoice_text = (
            (sensevoice_result or {}).get("text") or ""
        ).strip()

        if sensevoice_text:
            language = self._pick_language({}, sensevoice_result or {})
            if language.lower() != _EN_LANGUAGE:
                # 本地中文结果即为最终结果：不调用云端
                return self._merge(None, sensevoice_result)
            # 英文：补调云端提升转写质量
            assemblyai_result = self._call_provider(
                self._assemblyai, audio_bytes, "AssemblyAI 云端"
            )
            return self._merge(assemblyai_result, sensevoice_result)

        # 本地无可靠文本：仅用云端兜底
        assemblyai_result = self._call_provider(
            self._assemblyai, audio_bytes, "AssemblyAI 云端兜底"
        )
        return self._merge(assemblyai_result, sensevoice_result)

    def _call_provider(self, provider, audio_bytes: bytes, label: str):
        """在工作线程中调用单个 Provider，异常时返回 None 不抛出"""
        if not self._provider_ready(provider):
            return None
        executor = self._ensure_executor()
        try:
            future = executor.submit(
                provider.transcribe_and_analyze, audio_bytes
            )
            return future.result()
        except Exception:
            logger.warning("%s 调用失败", label, exc_info=True)
            return None

    def _merge(self, assemblyai_result: dict, sensevoice_result: dict) -> dict:
        """按语言与可用性合并两个 Provider 的结果"""
        assemblyai_result = assemblyai_result or {}
        sensevoice_result = sensevoice_result or {}

        # 语言：优先 SenseVoice 的语种识别，失败时退回 AssemblyAI
        language = self._pick_language(
            assemblyai_result, sensevoice_result
        )

        # 文本：按语言分流
        # - 英文：AssemblyAI 转录更准，优先采用
        # - 中文等其他语言：SenseVoice 本地转录更准（AssemblyAI 被配置为
        #   英语模型，转写中文不准），优先采用
        if language.lower() == _EN_LANGUAGE:
            text = (assemblyai_result.get("text") or "").strip()
            if not text:
                text = (sensevoice_result.get("text") or "").strip()
        else:
            text = (sensevoice_result.get("text") or "").strip()
            if not text:
                text = (assemblyai_result.get("text") or "").strip()

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
        if confidence <= 0.0 or not assemblyai_result.get("segments"):
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
