# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音服务提供方抽象接口

所有具体 provider（AssemblyAI、SenseVoice、其他云端/本地模型）
都应实现此接口，返回统一结构，方便上层切换
"""

from abc import ABC, abstractmethod


class BaseVoiceProvider(ABC):
    """语音识别 + 情绪分析提供方抽象基类"""

    #: provider 名称，用于日志与配置
    name: str = "base"

    @abstractmethod
    def is_ready(self) -> bool:
        """是否已准备好（API Key 配置、模型加载等）"""

    @abstractmethod
    def transcribe_and_analyze(self, audio_bytes: bytes) -> dict:
        """对一段音频做转录和情绪分析。

        Args:
            audio_bytes: 16kHz / 16bit / 单声道 PCM 原始字节

        Returns:
            统一结构：
            {
                "text": str,
                "sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE" | "UNKNOWN",
                "confidence": float,
                "segments": [   # 逐句结果
                    {"text": str, "sentiment": str, "confidence": float,
                     "start_ms": int, "end_ms": int},
                    ...
                ],
                "raw": dict,    # 原始返回
            }
        """

    def close(self) -> None:
        """释放资源，默认无操作。"""
        return None
