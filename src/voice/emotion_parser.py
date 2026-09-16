# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""情绪结果归一化

把 provider 返回的 POSITIVE / NEUTRAL / NEGATIVE
映射到系统内部统一的情绪标签
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


class EmotionParser:
    """情绪标签映射与过滤"""

    def __init__(self, min_confidence: float = 0.5):
        self._min_confidence = min_confidence

    def parse(self, provider_result: dict) -> dict:
        """把 provider 结果转成系统统一结构"""
        if not provider_result:
            return self._empty()

        sentiment = (provider_result.get("sentiment") or "UNKNOWN").upper()
        confidence = float(provider_result.get("confidence") or 0.0)

        if confidence < self._min_confidence:
            emotion = EMOTION_UNKNOWN
        else:
            emotion = self._map_sentiment(sentiment)

        # 逐句也做映射
        segments = []
        for seg in provider_result.get("segments", []):
            seg_conf = float(seg.get("confidence") or 0.0)
            seg_emo = (
                self._map_sentiment((seg.get("sentiment") or "").upper())
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
            "sentiment": sentiment,
            "confidence": confidence,
            "segments": segments,
        }

    def _map_sentiment(self, sentiment: str) -> str:
        mapping = {
            "POSITIVE": EMOTION_HAPPY,
            "NEUTRAL": EMOTION_NEUTRAL,
            "NEGATIVE": EMOTION_SAD,
        }
        return mapping.get(sentiment, EMOTION_UNKNOWN)

    def _empty(self) -> dict:
        return {
            "text": "",
            "emotion": EMOTION_UNKNOWN,
            "sentiment": "UNKNOWN",
            "confidence": 0.0,
            "segments": [],
        }
