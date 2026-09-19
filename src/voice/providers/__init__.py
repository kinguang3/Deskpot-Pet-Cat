# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""语音服务提供方。"""

from src.voice.providers.base import BaseVoiceProvider
from src.voice.providers.hybrid_provider import HybridVoiceProvider

__all__ = ["BaseVoiceProvider", "HybridVoiceProvider"]
