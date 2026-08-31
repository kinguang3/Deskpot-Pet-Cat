# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""行为控制器模块

集中管理 Nina 的自主行为决策、状态转换优先级、无互动睡眠。
所有状态切换通过此模块统一发起。
"""

import random
import time

from PySide6.QtCore import QTimer, QObject

from src.behavior.state_machine import StateMachine
from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 行为参数（从 config 读取，此处为默认值）
DEFAULT_AUTO_SLEEP_TIMEOUT = 300  # 5 分钟
DEFAULT_CHECK_INTERVAL = 1000  # 1 秒
DEFAULT_IDLE_MIN = 5000
DEFAULT_IDLE_MAX = 15000
DEFAULT_WALK_MIN = 3000
DEFAULT_WALK_MAX = 8000
DEFAULT_STOP_MIN = 2000
DEFAULT_STOP_MAX = 6000
DEFAULT_WATCH_MIN = 2000
DEFAULT_WATCH_MAX = 4000


class BehaviorController(QObject):
    """集中式行为控制器。

    职责：
    - 管理自主行为决策（idle → walk/stop/watch → idle）
    - 跟踪用户最后互动时间
    - 超时自动进入 sleep
    - sleep 时阻止自主行为
    - 用户互动时重置行为计时器
    """

    def __init__(self, state_machine: StateMachine, parent=None):
        super().__init__(parent)
        self._sm = state_machine
        self._event_bus = EventBus()
        self._config = ConfigManager()

        # 互动追踪
        self._last_interact_time: float = time.time()

        # 行为参数
        self._auto_sleep_timeout = self._config.get(
            "behavior.auto_sleep_timeout", DEFAULT_AUTO_SLEEP_TIMEOUT
        )
        self._idle_min = self._config.get("behavior.idle_duration_min", DEFAULT_IDLE_MIN)
        self._idle_max = self._config.get("behavior.idle_duration_max", DEFAULT_IDLE_MAX)
        self._walk_min = self._config.get("behavior.walk_duration_min", DEFAULT_WALK_MIN)
        self._walk_max = self._config.get("behavior.walk_duration_max", DEFAULT_WALK_MAX)

        # Debug 模式下缩短超时
        if self._config.get("app.debug", False):
            debug_timeout = self._config.get("behavior.debug_sleep_timeout", 10)
            self._auto_sleep_timeout = debug_timeout
            logger.info("Debug mode: auto sleep timeout = %ds", debug_timeout)

        # 自主行为定时器（idle 状态下的决策）
        self._behavior_timer = QTimer(self)
        self._behavior_timer.timeout.connect(self._on_behavior_tick)

        # 无互动检查定时器
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.timeout.connect(self._on_inactivity_check)

        # 连接事件
        self._event_bus.on("interaction.single_click", self._on_user_interaction)
        self._event_bus.on("interaction.double_click", self._on_user_interaction)
        self._event_bus.on("interaction.right_click", self._on_user_interaction)
        self._event_bus.on("interaction.hover_enter", self._on_hover_enter)
        self._event_bus.on("window.mouse_released", self._on_drag_end)
        self._event_bus.on("state.changed", self._on_state_changed)

        logger.info(
            "BehaviorController initialized (sleep timeout: %ds)",
            self._auto_sleep_timeout,
        )

    @property
    def seconds_since_interact(self) -> float:
        return time.time() - self._last_interact_time

    def start(self):
        """启动行为控制。"""
        self._behavior_timer.start(DEFAULT_CHECK_INTERVAL)
        self._inactivity_timer.start(DEFAULT_CHECK_INTERVAL)
        logger.info("BehaviorController started")

    def stop(self):
        """停止所有计时器。"""
        self._behavior_timer.stop()
        self._inactivity_timer.stop()

    def refresh_interaction(self):
        """刷新最后互动时间。"""
        self._last_interact_time = time.time()

    # ─── 自主行为决策 ───

    def _on_behavior_tick(self):
        """自主行为决策（仅在 idle 状态触发）。"""
        if not self._sm.is_state("idle"):
            return

        roll = random.random()
        if roll < 0.25:
            self._sm.transition_to("walk")
        elif roll < 0.40:
            self._sm.transition_to("stop")
        elif roll < 0.55:
            self._sm.transition_to("watch")
        else:
            # 保持 idle，重新设定延迟
            delay = random.randint(self._idle_min, self._idle_max)
            self._behavior_timer.start(delay)

    def _on_state_changed(self, data: dict):
        """状态变化后重新安排自主行为计时器。"""
        new_state = data.get("to", "")

        # 自主行为只在 idle 状态触发
        if new_state == "idle":
            delay = random.randint(self._idle_min, self._idle_max)
            self._behavior_timer.start(delay)
        elif new_state == "stop":
            # stop 结束后回到 idle
            delay = random.randint(DEFAULT_STOP_MIN, DEFAULT_STOP_MAX)
            self._behavior_timer.start(delay)
        elif new_state == "walk":
            delay = random.randint(self._walk_min, self._walk_max)
            self._behavior_timer.start(delay)
        elif new_state == "watch":
            delay = random.randint(DEFAULT_WATCH_MIN, DEFAULT_WATCH_MAX)
            self._behavior_timer.start(delay)
        elif new_state in ("sleep", "dragged", "clicked"):
            # 这些状态下暂停自主行为
            self._behavior_timer.stop()

    # ─── 无互动 → 睡眠 ───

    def _on_inactivity_check(self):
        """定期检查是否超时进入睡眠。"""
        current = self._sm.current_state_name

        # 已经在 sleep 或 dragged 不需要检查
        if current in ("sleep", "dragged"):
            return

        if self.seconds_since_interact >= self._auto_sleep_timeout:
            logger.info(
                "Inactivity timeout reached (%.0fs >= %ds)",
                self.seconds_since_interact,
                self._auto_sleep_timeout,
            )
            self._sm.transition_to("sleep")

    # ─── 用户互动处理 ───

    def _on_user_interaction(self, data: dict):
        """用户点击/双击/右键 → 刷新互动时间 + 响应。"""
        self.refresh_interaction()

        current = self._sm.current_state_name

        # sleep 状态下点击 → 唤醒
        if current == "sleep":
            self._sm.transition_to("idle")
            logger.debug("User clicked sleeping Nina -> wake")
            return

        # 其他状态 → 进入 clicked 反应
        if current not in ("dragged", "clicked"):
            self._sm.transition_to("clicked")

    def _on_hover_enter(self, data: dict):
        """鼠标进入 Nina 区域 → 刷新互动时间。"""
        self.refresh_interaction()

    def _on_drag_end(self, data: dict):
        """拖动结束 → 回到 idle。"""
        if self._sm.is_state("dragged"):
            self._sm.transition_to("idle")

    # ─── 外部调用接口 ───

    def on_drag_start(self):
        """拖动开始 → 进入 dragged，暂停自主行为。"""
        self.refresh_interaction()
        self._behavior_timer.stop()
        self._sm.transition_to("dragged")
