# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""微行为模块

管理 Nina 的短小动作（blink, stretch, yawn 等）。
这些行为非常短暂，用于增加生命感。
使用现有的单帧图片（tall, long, melt, glitch）。
"""

import random
import time

from PySide6.QtCore import QTimer, QObject

from src.animation.manager import AnimationManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 微行为定义
MICRO_BEHAVIORS = {
    "stretch": {
        "animation": "tall",       # 使用 tall 单帧
        "duration": 800,           # 毫秒
        "cooldown": 60,            # 秒
        "description": "伸懒腰",
    },
    "yawn": {
        "animation": "long",       # 使用 long 单帧
        "duration": 1200,
        "cooldown": 90,
        "description": "打哈欠",
    },
    "relax": {
        "animation": "melt",       # 使用 melt 单帧
        "duration": 1500,
        "cooldown": 45,
        "description": "放松",
    },
    "surprise": {
        "animation": "glitch",     # 使用 glitch 单帧
        "duration": 600,
        "cooldown": 30,
        "description": "惊讶",
    },
}


class MicroBehavior(QObject):
    """微行为管理器。

    在 idle 状态下随机触发短暂的小动作。
    """

    def __init__(self, anim_manager: AnimationManager, parent=None):
        super().__init__(parent)
        self._anim = anim_manager
        self._event_bus = EventBus()

        # 微行为定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)

        # 冷却记录
        self._last_run: dict[str, float] = {}

        # 当前是否在播放微行为
        self._playing: bool = False

        # 上一次播放的动画名（用于恢复）
        self._previous_animation: str = ""

        logger.debug("MicroBehavior initialized")

    def start(self):
        """启动微行为系统。"""
        self._schedule_next()
        logger.debug("MicroBehavior started")

    def stop(self):
        """停止微行为系统。"""
        self._timer.stop()

    def _schedule_next(self):
        """安排下一次微行为检查（10-30秒后）。"""
        delay = random.randint(10000, 30000)
        self._timer.start(delay)

    def _on_timer_tick(self):
        """定时器触发 → 尝试播放微行为。"""
        if self._playing:
            self._schedule_next()
            return

        # 随机选择一个微行为
        behavior_name = self._choose_behavior()
        if behavior_name:
            self._play_micro_behavior(behavior_name)

        self._schedule_next()

    def _choose_behavior(self) -> str | None:
        """选择一个可以播放的微行为。"""
        now = time.time()
        candidates = []

        for name, config in MICRO_BEHAVIORS.items():
            # 检查冷却
            last = self._last_run.get(name, 0)
            if now - last < config["cooldown"]:
                continue
            candidates.append(name)

        if not candidates:
            return None

        return random.choice(candidates)

    def _play_micro_behavior(self, behavior_name: str):
        """播放微行为。"""
        config = MICRO_BEHAVIORS.get(behavior_name)
        if not config:
            return

        # 记录当前动画（播放完后恢复）
        self._previous_animation = self._anim.current_animation

        # 播放微行为动画（单帧）
        self._anim.play(config["animation"], loop=False)
        self._playing = True

        # 记录冷却
        self._last_run[behavior_name] = time.time()

        logger.debug("Micro behavior: %s", config["description"])

        # 定时恢复原动画
        QTimer.singleShot(config["duration"], self._on_micro_behavior_end)

    def _on_micro_behavior_end(self):
        """微行为结束，恢复原动画。"""
        self._playing = False
        if self._previous_animation:
            self._anim.play(self._previous_animation, loop=True)
            logger.debug("Restored animation: %s", self._previous_animation)

    def force_play(self, behavior_name: str):
        """强制播放微行为（外部调用）。"""
        if behavior_name in MICRO_BEHAVIORS:
            self._play_micro_behavior(behavior_name)

    def get_debug_info(self) -> dict:
        """获取调试信息。"""
        now = time.time()
        cooldowns = {}
        for name, config in MICRO_BEHAVIORS.items():
            last = self._last_run.get(name, 0)
            remaining = max(0, config["cooldown"] - (now - last))
            cooldowns[name] = round(remaining, 1)

        return {
            "playing": self._playing,
            "cooldowns": cooldowns,
        }
