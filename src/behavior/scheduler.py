# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""行为调度器模块

根据 Nina 的内部状态计算行为权重，选择下一个行为。
替代完全随机选择，让行为更自然。
"""

import random
import time
from typing import Optional

from src.behavior.time_context import TimeContext
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 行为名称常量
BEHAVIOR_WALK = "walk"
BEHAVIOR_STOP = "stop"
BEHAVIOR_WATCH = "watch"
BEHAVIOR_IDLE = "idle"
BEHAVIOR_SLEEP = "sleep"
BEHAVIOR_HAPPY = "happy"
BEHAVIOR_LOOK = "look"


class BehaviorScheduler:
    """加权行为调度器。

    根据内部状态计算每个行为的权重，
    然后用加权随机选择下一个行为。
    """

    def __init__(self):
        # 时间上下文
        self._time_context = TimeContext()

        # 基础权重（无状态影响时的默认值）
        self._base_weights: dict[str, float] = {
            BEHAVIOR_WALK: 25,
            BEHAVIOR_STOP: 15,
            BEHAVIOR_WATCH: 20,
            BEHAVIOR_IDLE: 35,
            BEHAVIOR_SLEEP: 0,   # sleep 由 inactivity 触发，不由 scheduler 主动选
            BEHAVIOR_HAPPY: 5,
        }

        # 最终权重（每次选择前重新计算）
        self._current_weights: dict[str, float] = {}

        # 行为冷却时间（秒）
        self._cooldowns: dict[str, float] = {
            BEHAVIOR_WALK: 10,
            BEHAVIOR_STOP: 5,
            BEHAVIOR_WATCH: 8,
            BEHAVIOR_HAPPY: 30,
        }

        # 上次执行每种行为的时间
        self._last_run: dict[str, float] = {}

        # 最近行为历史（最近 N 次行为）
        self._history: list[str] = []
        self._history_max: int = 8

        # 内部状态引用（由 EmotionSystem 注入）
        self._energy: float = 80.0
        self._happiness: float = 70.0
        self._curiosity: float = 60.0
        self._sleepiness: float = 20.0
        self._affection: float = 40.0

        logger.debug("BehaviorScheduler initialized")

    # ─── 状态注入 ───

    def update_emotions(
        self,
        energy: float = 80.0,
        happiness: float = 70.0,
        curiosity: float = 60.0,
        sleepiness: float = 20.0,
        affection: float = 40.0,
    ):
        """更新内部状态（由 EmotionSystem 定期调用）。"""
        self._energy = max(0, min(100, energy))
        self._happiness = max(0, min(100, happiness))
        self._curiosity = max(0, min(100, curiosity))
        self._sleepiness = max(0, min(100, sleepiness))
        self._affection = max(0, min(100, affection))

    # ─── 核心：加权选择 ───

    def choose_behavior(self, current_state: str) -> Optional[str]:
        """根据当前状态和内部情感，选择下一个行为。

        Args:
            current_state: 当前行为状态名

        Returns:
            选择的行为名，None 表示保持当前状态
        """
        self._calculate_weights()

        # 过滤掉不可选的行为
        candidates = {}
        for name, weight in self._current_weights.items():
            if weight <= 0:
                continue
            # 不能选择当前正在执行的行为
            if name == current_state:
                continue
            # 检查冷却
            if self._is_on_cooldown(name):
                continue
            candidates[name] = weight

        if not candidates:
            return None

        # 加权随机选择
        chosen = self._weighted_select(candidates)

        if chosen:
            self._last_run[chosen] = time.time()
            self._record_history(chosen)
            logger.debug(
                "Behavior chosen: %s (weights: %s)",
                chosen,
                {k: round(v, 1) for k, v in candidates.items()},
            )

        return chosen

    def _calculate_weights(self):
        """根据内部状态计算最终权重。"""
        w = dict(self._base_weights)

        # Energy 影响
        # Energy 高 → walk/happy 增加
        # Energy 低 → idle/sleep 增加
        energy_factor = self._energy / 100.0
        w[BEHAVIOR_WALK] *= 0.5 + energy_factor
        w[BEHAVIOR_HAPPY] *= 0.5 + energy_factor
        w[BEHAVIOR_IDLE] *= 1.5 - energy_factor

        # Sleepiness 影响
        # Sleepiness 高 → idle 增加, walk 减少
        sleep_factor = self._sleepiness / 100.0
        w[BEHAVIOR_IDLE] *= 0.5 + sleep_factor
        w[BEHAVIOR_WALK] *= 1.2 - sleep_factor * 0.8
        w[BEHAVIOR_HAPPY] *= 1.0 - sleep_factor * 0.5

        # Curiosity 影响
        # Curiosity 高 → watch 增加
        curiosity_factor = self._curiosity / 100.0
        w[BEHAVIOR_WATCH] *= 0.5 + curiosity_factor * 1.5

        # Happiness 影响
        # Happiness 高 → happy 增加
        happiness_factor = self._happiness / 100.0
        w[BEHAVIOR_HAPPY] *= 0.3 + happiness_factor * 1.5

        # Affection 影响
        # Affection 高 → watch(看用户) 增加
        affection_factor = self._affection / 100.0
        w[BEHAVIOR_WATCH] *= 0.8 + affection_factor * 0.4

        # 时间上下文修正
        time_modifiers = self._time_context.get_all_modifiers()
        for behavior, modifier in time_modifiers.items():
            if behavior in w:
                w[behavior] *= modifier

        # 行为历史惩罚：最近做过的行为降低权重
        for recent_behavior in self._history[-3:]:
            if recent_behavior in w:
                w[recent_behavior] *= 0.5

        self._current_weights = w

    def _weighted_select(self, candidates: dict[str, float]) -> Optional[str]:
        """加权随机选择。"""
        if not candidates:
            return None

        total = sum(candidates.values())
        if total <= 0:
            return None

        roll = random.uniform(0, total)
        cumulative = 0.0
        for name, weight in candidates.items():
            cumulative += weight
            if roll <= cumulative:
                return name

        # 兜底：返回最后一个
        return list(candidates.keys())[-1]

    # ─── 冷却系统 ───

    def _is_on_cooldown(self, behavior: str) -> bool:
        """检查行为是否在冷却中。"""
        if behavior not in self._cooldowns:
            return False
        if behavior not in self._last_run:
            return False
        elapsed = time.time() - self._last_run[behavior]
        return elapsed < self._cooldowns[behavior]

    def get_cooldown_remaining(self, behavior: str) -> float:
        """获取行为剩余冷却时间（秒）。"""
        if behavior not in self._cooldowns:
            return 0.0
        if behavior not in self._last_run:
            return 0.0
        elapsed = time.time() - self._last_run[behavior]
        remaining = self._cooldowns[behavior] - elapsed
        return max(0.0, remaining)

    # ─── 行为历史 ───

    def _record_history(self, behavior: str):
        """记录行为到历史。"""
        self._history.append(behavior)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max:]

    def get_history(self) -> list[str]:
        """获取最近行为历史。"""
        return list(self._history)

    @property
    def time_context(self) -> TimeContext:
        """获取时间上下文。"""
        return self._time_context

    def get_weights_debug(self) -> dict[str, float]:
        """获取当前权重（调试用）。"""
        self._calculate_weights()
        return {k: round(v, 1) for k, v in self._current_weights.items() if v > 0}
