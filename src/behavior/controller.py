# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""行为控制器模块

集中管理 Nina 的自主行为决策、状态转换优先级、无互动睡眠。
所有状态切换通过此模块统一发起。
"""

import random
import time

from PySide6.QtCore import QTimer, QObject
from PySide6.QtGui import QCursor

from src.behavior.state_machine import StateMachine
from src.behavior.scheduler import BehaviorScheduler
from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 行为参数默认值
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
    - 通过 BehaviorScheduler 加权选择下一个行为
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

        # 行为调度器（加权选择）
        self._scheduler = BehaviorScheduler()

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

        # 鼠标感知定时器（每2秒检查一次鼠标位置）
        self._mouse_awareness_timer = QTimer(self)
        self._mouse_awareness_timer.timeout.connect(self._on_mouse_awareness_check)
        self._mouse_awareness_radius = 150  # 像素，鼠标接近范围
        self._mouse_awareness_cooldown = 0  # 上次触发时间
        self._mouse_awareness_min_interval = 10  # 最小触发间隔（秒）

        # 窗口引用（用于获取位置，由 App 设置）
        self._window = None

        # 连接事件
        self._event_bus.on("interaction.single_click", self._on_user_interaction)
        self._event_bus.on("interaction.double_click", self._on_user_interaction)
        self._event_bus.on("interaction.right_click", self._on_user_interaction)
        self._event_bus.on("interaction.hover_enter", self._on_hover_enter)
        self._event_bus.on("window.mouse_released", self._on_drag_end)
        self._event_bus.on("state.changed", self._on_state_changed)
        self._event_bus.on("voice.wake_detected", self._on_voice_wake)

        logger.info(
            "BehaviorController initialized (sleep timeout: %ds)",
            self._auto_sleep_timeout,
        )

    @property
    def scheduler(self) -> BehaviorScheduler:
        """获取行为调度器（供 EmotionSystem 注入状态）。"""
        return self._scheduler

    @property
    def seconds_since_interact(self) -> float:
        return time.time() - self._last_interact_time

    def start(self):
        """启动行为控制。"""
        self._behavior_timer.start(DEFAULT_CHECK_INTERVAL)
        self._inactivity_timer.start(DEFAULT_CHECK_INTERVAL)
        self._mouse_awareness_timer.start(2000)  # 每2秒检查鼠标
        logger.info("BehaviorController started")

    def set_window(self, window):
        """设置窗口引用（用于鼠标感知）。"""
        self._window = window

    def stop(self):
        """停止所有计时器。"""
        self._behavior_timer.stop()
        self._inactivity_timer.stop()

    def refresh_interaction(self):
        """刷新最后互动时间。"""
        self._last_interact_time = time.time()

    # ─── 自主行为决策（使用 Scheduler） ───

    def _on_behavior_tick(self):
        """自主行为决策（仅在 idle 状态触发）。"""
        if not self._sm.is_state("idle"):
            return

        chosen = self._scheduler.choose_behavior("idle")

        if chosen is None:
            # 没有可选行为，保持 idle
            delay = random.randint(self._idle_min, self._idle_max)
            self._behavior_timer.start(delay)
            return

        if chosen == "idle":
            # scheduler 建议继续 idle
            delay = random.randint(self._idle_min, self._idle_max)
            self._behavior_timer.start(delay)
            return

        # 切换到选择的行为
        self._sm.transition_to(chosen)

    def _on_state_changed(self, data: dict):
        """状态变化后重新安排自主行为计时器。"""
        new_state = data.get("to", "")

        if new_state == "idle":
            delay = random.randint(self._idle_min, self._idle_max)
            self._behavior_timer.start(delay)
        elif new_state == "stop":
            delay = random.randint(DEFAULT_STOP_MIN, DEFAULT_STOP_MAX)
            self._behavior_timer.start(delay)
        elif new_state == "walk":
            delay = random.randint(self._walk_min, self._walk_max)
            self._behavior_timer.start(delay)
        elif new_state == "watch":
            delay = random.randint(DEFAULT_WATCH_MIN, DEFAULT_WATCH_MAX)
            self._behavior_timer.start(delay)
        elif new_state in ("sleep", "dragged", "clicked", "happy", "wake"):
            self._behavior_timer.stop()

    # ─── 无互动 → 睡眠 ───

    def _on_inactivity_check(self):
        """定期检查是否超时进入睡眠。"""
        current = self._sm.current_state_name
        if current in ("sleep", "dragged"):
            return

        if self.seconds_since_interact >= self._auto_sleep_timeout:
            logger.info(
                "Inactivity timeout reached (%.0fs >= %ds)",
                self.seconds_since_interact,
                self._auto_sleep_timeout,
            )
            self._sm.transition_to("sleep")

    # ─── 鼠标感知 ───

    def _on_mouse_awareness_check(self):
        """检查鼠标是否接近 Nina，触发反应。"""
        if self._window is None:
            return

        current = self._sm.current_state_name

        # 已经在交互状态或睡着，不触发
        if current in ("sleep", "dragged", "clicked", "walk"):
            return

        # 冷却检查
        now = time.time()
        if now - self._mouse_awareness_cooldown < self._mouse_awareness_min_interval:
            return

        # 获取鼠标和窗口位置
        mouse_pos = QCursor.pos()
        window_center = self._window.mapToGlobal(
            self._window.rect().center()
        )

        # 计算距离
        dx = mouse_pos.x() - window_center.x()
        dy = mouse_pos.y() - window_center.y()
        distance = (dx * dx + dy * dy) ** 0.5

        # 鼠标在接近范围内
        if distance < self._mouse_awareness_radius:
            # 有概率触发 watch 反应
            if random.random() < 0.4:
                self._sm.transition_to("watch")
                self._mouse_awareness_cooldown = now
                logger.debug(
                    "Mouse awareness triggered (distance: %.0fpx)", distance
                )

    # ─── 用户互动处理 ───

    def _on_user_interaction(self, data: dict):
        """用户点击/双击/右键 → 刷新互动时间 + 响应。"""
        self.refresh_interaction()

        current = self._sm.current_state_name

        if current == "sleep":
            self._sm.transition_to("idle")
            logger.debug("User clicked sleeping Nina -> wake")
            return

        if current not in ("dragged", "clicked"):
            self._sm.transition_to("clicked")

    def _on_hover_enter(self, data: dict):
        """鼠标进入 Nina 区域 → 刷新互动时间。"""
        self.refresh_interaction()

    def _on_drag_end(self, data: dict):
        """拖动结束 → 回到 idle。"""
        if self._sm.is_state("dragged"):
            self._sm.transition_to("idle")

    # ─── 语音唤醒 ───

    def _on_voice_wake(self, data: dict):
        """语音唤醒事件 → 调度到主线程执行 wake 状态切换。"""
        # 语音检测在后台线程，Qt 操作必须在主线程
        QTimer.singleShot(0, self._do_voice_wake)

    def _do_voice_wake(self):
        """在主线程执行语音唤醒。"""
        self.refresh_interaction()

        current = self._sm.current_state_name

        # 已经在 wake 或 clicked 状态，不重复触发
        if current in ("wake", "clicked"):
            return

        # 进入 wake 状态
        self._behavior_timer.stop()
        self._sm.transition_to("wake")
        logger.debug("Voice wake triggered from state: %s", current)

    # ─── 外部调用接口 ───

    def on_drag_start(self):
        """拖动开始 → 进入 dragged，暂停自主行为。"""
        self.refresh_interaction()
        self._behavior_timer.stop()

        # 如果在睡觉，先唤醒
        if self._sm.is_state("sleep"):
            self._sm.transition_to("idle")

        self._sm.transition_to("dragged")

    def get_debug_info(self) -> dict:
        """获取调试信息。"""
        return {
            "state": self._sm.current_state_name,
            "seconds_since_interact": round(self.seconds_since_interact, 1),
            "auto_sleep_timeout": self._auto_sleep_timeout,
            "scheduler_weights": self._scheduler.get_weights_debug(),
            "scheduler_history": self._scheduler.get_history(),
        }
