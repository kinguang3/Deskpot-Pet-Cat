# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""情感系统模块

管理 Nina 的内部情感状态：
- Energy: 精力（影响 walk/happy 概率）
- Happiness: 快乐（影响 happy 概率）
- Curiosity: 好奇心（影响 watch 概率）
- Sleepiness: 困倦（影响 idle/sleep 概率）
- Affection: 依恋（影响 watch/互动 概率）

数值缓慢变化，不会大幅波动。
"""

import time

from PySide6.QtCore import QTimer, QObject

from src.behavior.scheduler import BehaviorScheduler
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 默认情感值
DEFAULT_ENERGY = 80.0
DEFAULT_HAPPINESS = 70.0
DEFAULT_CURIOSITY = 60.0
DEFAULT_SLEEPILESS = 20.0
DEFAULT_AFFECTION = 40.0

# 情感变化速率（每秒）
DECAY_RATE = 0.02        # 自然衰减
RECOVER_RATE = 0.01      # 精力恢复（idle时）
SLEEP_DRAIN = 0.05       # 困倦增长速率
WAKE_RECOVER = 0.3       # 醒来时精力恢复


class EmotionSystem(QObject):
    """Nina 的内部情感系统。

    定期更新情感值，注入到 BehaviorScheduler。
    情感值影响行为权重。
    """

    def __init__(self, scheduler: BehaviorScheduler, parent=None):
        super().__init__(parent)
        self._scheduler = scheduler
        self._event_bus = EventBus()

        # 情感值（0-100）
        self._energy: float = DEFAULT_ENERGY
        self._happiness: float = DEFAULT_HAPPINESS
        self._curiosity: float = DEFAULT_CURIOSITY
        self._sleepiness: float = DEFAULT_SLEEPILESS
        self._affection: float = DEFAULT_AFFECTION

        # 当前状态（用于判断是否需要特殊更新）
        self._current_state: str = "idle"

        # 情感更新定时器（每2秒更新一次，足够平滑）
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_update)

        # 监听状态变化
        self._event_bus.on("state.changed", self._on_state_changed)

        logger.debug("EmotionSystem initialized")

    # ─── 属性 ───

    @property
    def energy(self) -> float:
        return self._energy

    @property
    def happiness(self) -> float:
        return self._happiness

    @property
    def curiosity(self) -> float:
        return self._curiosity

    @property
    def sleepiness(self) -> float:
        return self._sleepiness

    @property
    def affection(self) -> float:
        return self._affection

    # ─── 生命周期 ───

    def start(self):
        """启动情感系统。"""
        self._update_timer.start(2000)  # 每2秒更新
        self._sync_to_scheduler()
        logger.info("EmotionSystem started")

    def stop(self):
        """停止情感系统。"""
        self._update_timer.stop()

    # ─── 核心更新 ───

    def _on_update(self):
        """定时更新情感值。"""
        # 自然衰减：所有情感缓慢向中间值回归
        self._energy = self._decay(self._energy, 50.0, DECAY_RATE)
        self._happiness = self._decay(self._happiness, 50.0, DECAY_RATE)
        self._curiosity = self._decay(self._curiosity, 50.0, DECAY_RATE * 0.5)
        self._affection = self._decay(self._affection, 50.0, DECAY_RATE * 0.3)

        # 困倦根据状态变化
        if self._current_state == "sleep":
            # 睡觉时困倦快速下降
            self._sleepiness = max(0, self._sleepiness - 0.5)
            # 精力恢复
            self._energy = min(100, self._energy + 0.3)
        elif self._current_state == "idle":
            # idle 时精力缓慢恢复，困倦缓慢增长
            self._energy = min(100, self._energy + RECOVER_RATE)
            self._sleepiness = min(100, self._sleepiness + SLEEP_DRAIN * 0.3)
        elif self._current_state == "walk":
            # walk 消耗精力
            self._energy = max(0, self._energy - 0.1)
            self._sleepiness = min(100, self._sleepiness + SLEEP_DRAIN * 0.2)
        elif self._current_state in ("watch", "stop"):
            # 观察时好奇心满足
            self._curiosity = max(0, self._curiosity - 0.05)

        self._sync_to_scheduler()

    def _decay(self, current: float, target: float, rate: float) -> float:
        """向目标值缓慢衰减。"""
        diff = current - target
        if abs(diff) < 0.1:
            return target
        return current - diff * rate

    def _sync_to_scheduler(self):
        """将情感值同步到 Scheduler。"""
        self._scheduler.update_emotions(
            energy=self._energy,
            happiness=self._happiness,
            curiosity=self._curiosity,
            sleepiness=self._sleepiness,
            affection=self._affection,
        )

    # ─── 外部事件影响 ───

    def _on_state_changed(self, data: dict):
        """状态变化回调。"""
        self._current_state = data.get("to", "")

    def on_user_click(self):
        """用户点击 → 快乐↑ 依恋↑"""
        self._happiness = min(100, self._happiness + 3)
        self._affection = min(100, self._affection + 2)
        self._sleepiness = max(0, self._sleepiness - 1)
        logger.debug(
            "Emotion: click -> happiness=%.1f, affection=%.1f",
            self._happiness,
            self._affection,
        )

    def on_user_drag(self):
        """用户拖动 → 快乐小幅下降"""
        self._happiness = max(0, self._happiness - 1)
        logger.debug("Emotion: drag -> happiness=%.1f", self._happiness)

    def on_user_hover(self):
        """用户悬停 → 好奇心小幅上升"""
        self._curiosity = min(100, self._curiosity + 0.5)

    def on_wake(self):
        """被唤醒 → 精力恢复"""
        self._energy = min(100, self._energy + WAKE_RECOVER)
        self._happiness = min(100, self._happiness + 2)
        logger.debug(
            "Emotion: wake -> energy=%.1f, happiness=%.1f",
            self._energy,
            self._happiness,
        )

    def on_long_inactive(self):
        """长时间无互动 → 快乐下降，困倦上升"""
        self._happiness = max(0, self._happiness - 2)
        self._sleepiness = min(100, self._sleepiness + 5)
        logger.debug(
            "Emotion: long inactive -> happiness=%.1f, sleepiness=%.1f",
            self._happiness,
            self._sleepiness,
        )

    def on_walk_complete(self):
        """行走完成 → 好奇心满足"""
        self._curiosity = max(0, self._curiosity - 2)

    # ─── 调试 ───

    def get_debug_info(self) -> dict:
        """获取情感状态（调试用）。"""
        return {
            "energy": round(self._energy, 1),
            "happiness": round(self._happiness, 1),
            "curiosity": round(self._curiosity, 1),
            "sleepiness": round(self._sleepiness, 1),
            "affection": round(self._affection, 1),
        }
