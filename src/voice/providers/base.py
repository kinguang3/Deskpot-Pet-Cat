# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音服务提供方抽象接口

所有具体 provider（AssemblyAI、SenseVoice、其他云端/本地模型）
都应实现此接口，返回统一结构，方便上层切换
"""

from abc import ABC, abstractmethod

import concurrent.futures
import time

#: 关闭线程池时等待在途任务结束的上限（秒）
SHUTDOWN_GRACE_SECONDS = 2.0


def shutdown_executor_bounded(
    executor: concurrent.futures.ThreadPoolExecutor | None,
    pending_count,
    timeout: float = SHUTDOWN_GRACE_SECONDS,
) -> int:
    """有上限地关闭线程池，取消排队任务并最多等待 timeout 秒。

    `ThreadPoolExecutor.shutdown(wait=True)` 会等所有**运行中**的任务结束，
    而语音推理的最坏耗时等于 provider 超时（云端转录可达 60s）。该调用常发生在
    Qt 主线程的退出/停止路径上，无界等待会导致界面长时间"未响应"。

    Args:
        executor: 待关闭的线程池，None 时直接返回
        pending_count: 无参可调用对象，返回仍在运行的任务数（由调用方加锁）
        timeout: 最多等待秒数

    Returns:
        超时后仍在运行的任务数；0 表示已全部结束
    """
    if executor is None:
        return 0

    executor.shutdown(wait=False, cancel_futures=True)

    deadline = time.monotonic() + timeout
    while pending_count() > 0:
        if time.monotonic() >= deadline:
            break
        time.sleep(0.02)

    return pending_count()


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
