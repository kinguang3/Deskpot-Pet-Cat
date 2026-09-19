# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""情绪结果归一化

把 provider 返回的原生情绪标签（如 SenseVoice 的 HAPPY/SAD/ANGRY/...）
映射到系统内部统一的情绪标签

适配点：
- SenseVoice 直接输出具体情绪，不输出 POSITIVE/NEUTRAL/NEGATIVE 极性
- 当 confidence 缺省（None）时，视为完全可信（1.0）
- 额外透传 language / event 字段，便于下游使用
"""

from src.utils.logger import get_logger

logger = get_logger(__name__)


# 内部统一标签
EMOTION_HAPPY = "HAPPY"
EMOTION_CALM = "CALM"
EMOTION_ANGRY = "ANGRY"
EMOTION_SAD = "SAD"
EMOTION_NEUTRAL = "NEUTRAL"
EMOTION_UNKNOWN = "UNKNOWN"


# SenseVoice 原生情绪 -> 内部统一标签
# SenseVoiceSmall 支持：HAPPY / SAD / ANGRY / NEUTRAL /
#                       FEARFUL / DISGUSTED / SURPRISED / EMO_UNKNOWN
_SENSEVOICE_EMOTION_MAP = {
    "HAPPY": EMOTION_HAPPY,
    "SAD": EMOTION_SAD,
    "ANGRY": EMOTION_ANGRY,
    "NEUTRAL": EMOTION_NEUTRAL,
    "FEARFUL": EMOTION_SAD,  # 恐惧归入消极
    "DISGUSTED": EMOTION_ANGRY,  # 厌恶归入愤怒
    "SURPRISED": EMOTION_HAPPY,  # 惊讶归入积极
    "EMO_UNKNOWN": EMOTION_UNKNOWN,
}

# 兼容旧 provider（AssemblyAI 等）仍以极性方式返回的情况
_LEGACY_SENTIMENT_MAP = {
    "POSITIVE": EMOTION_HAPPY,
    "NEUTRAL": EMOTION_NEUTRAL,
    "NEGATIVE": EMOTION_SAD,
}


class EmotionParser:
    """情绪标签映射与过滤"""

    def __init__(self, min_confidence: float = 0.5):
        self._min_confidence = min_confidence

    def parse(self, provider_result: dict) -> dict:
        """把 provider 结果转成系统统一结构"""
        if not provider_result:
            return self._empty()

        # 优先使用 provider 直接给出的 emotion 字段
        raw_emotion = (provider_result.get("emotion") or "").upper()
        # 兼容旧 provider 的 sentiment 字段
        raw_sentiment = (provider_result.get("sentiment") or "").upper()

        # SenseVoice 不提供置信度，缺省视为 1.0
        raw_conf = provider_result.get("confidence", None)
        confidence = 1.0 if raw_conf is None else float(raw_conf)

        if confidence < self._min_confidence:
            emotion = EMOTION_UNKNOWN
        else:
            emotion = self._map_emotion(raw_emotion, raw_sentiment)

        # 逐句也做映射
        segments = []
        for seg in provider_result.get("segments", []):
            seg_conf_raw = seg.get("confidence", None)
            seg_conf = 1.0 if seg_conf_raw is None else float(seg_conf_raw)
            seg_emotion_raw = (seg.get("emotion") or "").upper()
            seg_sentiment_raw = (seg.get("sentiment") or "").upper()
            seg_emo = (
                self._map_emotion(seg_emotion_raw, seg_sentiment_raw)
                if seg_conf >= self._min_confidence
                else EMOTION_UNKNOWN
            )
            segments.append(
                {
                    "text": seg.get("text", ""),
                    "emotion": seg_emo,
                    "sentiment": seg.get("sentiment", "UNKNOWN"),
                    "confidence": seg_conf,
                    "start_ms": seg.get("start_ms", 0),
                    "end_ms": seg.get("end_ms", 0),
                }
            )

        return {
            "text": provider_result.get("text", ""),
            "emotion": emotion,
            "sentiment": provider_result.get("sentiment", "UNKNOWN"),
            "confidence": confidence,
            "language": provider_result.get("language", "UNKNOWN"),
            "event": provider_result.get("event", "UNKNOWN"),
            "emotion_source": provider_result.get(
                "emotion_source", "unknown"
            ),
            "segments": segments,
        }

    def _map_emotion(self, raw_emotion: str, raw_sentiment: str = "") -> str:
        """先查 SenseVoice 原生情绪映射，再退回旧极性映射"""
        if raw_emotion in _SENSEVOICE_EMOTION_MAP:
            return _SENSEVOICE_EMOTION_MAP[raw_emotion]
        if raw_sentiment in _LEGACY_SENTIMENT_MAP:
            return _LEGACY_SENTIMENT_MAP[raw_sentiment]
        return EMOTION_UNKNOWN

    def _empty(self) -> dict:
        return {
            "text": "",
            "emotion": EMOTION_UNKNOWN,
            "sentiment": "UNKNOWN",
            "confidence": 0.0,
            "language": "UNKNOWN",
            "event": "UNKNOWN",
            "emotion_source": "unknown",
            "segments": [],
        }
