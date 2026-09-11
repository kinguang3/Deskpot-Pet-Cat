# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""应用管理器模块

负责初始化和协调所有模块。
管理应用生命周期。
"""

import random
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QObject, QEvent, Qt

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.core.window import PetWindow
from src.core.pet import Pet
from src.animation.sprites import SpriteLoader
from src.animation.manager import AnimationManager
from src.behavior.state_machine import StateMachine
from src.behavior.states import (
    IdleState,
    WalkState,
    StopState,
    SleepState,
    WatchState,
    TypingState,
    ClickedState,
    DraggedState,
    HappyState,
    WakeState,
)
from src.behavior.controller import BehaviorController
from src.behavior.emotion import EmotionSystem
from src.behavior.memory import Memory
from src.voice import VoiceWakeManager
from src.voice.command_parser import Intent
from src.voice.commands.time_command import get_time_response
from src.voice.commands.open_browser_command import open_browser
from src.interaction.mouse import MouseInteraction
from src.dialogue.bubble import DialogueBubble
from src.dialogue.content import DialogueContent
from src.ui.tray import SystemTray
from src.ui.settings import SettingsPanel
from src.utils.storage import Storage
from src.utils.logger import get_logger

logger = get_logger(__name__)


class App(QObject):
    """应用主管理器。"""

    def __init__(self):
        super().__init__()
        logger.info("Application initializing...")

        # 基础设施
        self._config = ConfigManager()
        self._event_bus = EventBus()
        self._storage = Storage()

        # 精灵图加载器
        self._sprite_loader = SpriteLoader()

        # 动画管理器
        self._anim_manager = AnimationManager(self._sprite_loader)

        # 主窗口
        self._window = PetWindow()

        # 宠物实体
        self._pet = Pet(self._window, self._anim_manager)

        # 对话系统
        self._dialogue_bubble = DialogueBubble()
        self._dialogue_content = DialogueContent()

        # 行为状态机
        self._state_machine = StateMachine()
        self._setup_states()

        # 行为控制器（集中管理自主行为 + 无互动睡眠）
        self._behavior_controller = BehaviorController(self._state_machine)

        # 情感系统（管理内部状态，影响行为权重）
        self._emotion_system = EmotionSystem(
            self._behavior_controller.scheduler
        )

        # 记忆系统（持久化互动数据）
        self._memory = Memory(self._storage)

        # 语音唤醒系统
        self._voice_wake = VoiceWakeManager()

        # 交互系统
        self._mouse_interaction = MouseInteraction()

        # 系统托盘
        self._tray = SystemTray()

        # 设置面板
        self._settings_panel = None  # 按需创建

        # 对话定时器（仅用于随机对话气泡，与行为无关）
        self._dialogue_timer = QTimer(self)
        self._dialogue_timer.timeout.connect(self._random_dialogue)
        self._dialogue_timer.start(random.randint(30000, 60000))

        # 语音命令窗口定时器（唤醒后 5 秒内接收命令）
        self._command_window_timer = QTimer(self)
        self._command_window_timer.setSingleShot(True)
        self._command_window_timer.timeout.connect(
            self._on_command_window_timeout
        )
        self._command_window_active = False

        # 连接事件
        self._connect_events()

        # 安装事件过滤器
        self._window.installEventFilter(self)

        logger.info("Application initialized")

    def _setup_states(self):
        """注册并配置所有行为状态。"""
        self._state_machine.anim = self._anim_manager

        self._state_machine.add_state(IdleState())
        self._state_machine.add_state(WalkState())
        self._state_machine.add_state(StopState())
        self._state_machine.add_state(SleepState())
        self._state_machine.add_state(WatchState())
        self._state_machine.add_state(TypingState())
        self._state_machine.add_state(ClickedState())
        self._state_machine.add_state(DraggedState())
        self._state_machine.add_state(HappyState())
        self._state_machine.add_state(WakeState())

        self._state_machine.set_initial_state("idle")

    def _connect_events(self):
        """连接事件总线回调。"""
        # 托盘事件
        self._tray.show_requested.connect(self._show_window)
        self._tray.hide_requested.connect(self._hide_window)
        self._tray.settings_requested.connect(self._show_settings)
        self._tray.quit_requested.connect(self._quit)

        # 交互事件
        self._event_bus.on("interaction.single_click", self._on_pet_click)
        self._event_bus.on(
            "interaction.double_click", self._on_pet_double_click
        )
        self._event_bus.on("interaction.right_click", self._on_pet_right_click)
        self._event_bus.on("interaction.hover_enter", self._on_hover_enter)
        self._event_bus.on("interaction.hover_leave", self._on_hover_leave)

        # 窗口拖动事件
        self._event_bus.on(
            "window.mouse_pressed", self._on_window_mouse_pressed
        )

        # 状态变化事件
        self._event_bus.on("state.changed", self._on_state_changed)

        # 语音唤醒事件
        self._event_bus.on("voice.wake_detected", self._on_voice_wake)

        # 语音命令事件
        self._event_bus.on("voice.command_detected", self._on_voice_command)

    def start(self):
        """启动应用。"""
        logger.info("Application starting...")
        # 加载配置
        self._apply_config()

        # 显示窗口
        self._window.show_center()
        self._window.show()
        logger.info("Window shown")

        # 显示托盘
        self._tray.show()
        logger.info("Tray icon shown")

        # 启动宠物
        self._pet.start()

        # 设置窗口引用（用于鼠标感知）
        self._behavior_controller.set_window(self._window)

        # 启动行为控制器
        self._behavior_controller.start()

        # 启动情感系统
        self._emotion_system.start()

        # 启动语音唤醒
        self._voice_wake.start()

        # 显示问候语
        QTimer.singleShot(1000, self._show_greeting)

        logger.info("Application started")

    def _apply_config(self):
        """应用配置到各个模块。"""
        scale = self._config.get("window.size_scale", 1.0)
        self._window.set_scale(scale)

        opacity = self._config.get("window.opacity", 0.95)
        self._window.set_opacity(opacity)

    def _apply_settings_preview(self, settings: dict):
        """根据预览设置实时更新桌宠窗口"""
        # 大小缩放
        scale = settings.get("window.size_scale", 1.0)
        self._window.set_scale(scale)
        # 透明度
        opacity = settings.get("window.opacity", 0.95)
        self._window.setWindowOpacity(opacity)
        # 置顶
        topmost = settings.get("window.always_on_top", True)
        flags = self._window.windowFlags()
        if topmost:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self._window.setWindowFlags(flags)
        self._window.show()

    def _show_window(self):
        """显示窗口。"""
        self._window.show()
        self._window.show_center()
        logger.debug("Window shown via tray")

    def _hide_window(self):
        """隐藏窗口。"""
        self._window.hide()
        logger.debug("Window hidden via tray")

    def _show_settings(self):
        """显示设置面板。"""
        if self._settings_panel is None:
            self._settings_panel = SettingsPanel(
                voice_manager=self._voice_wake
            )
            self._settings_panel.settings_changed.connect(self._apply_config)
            self._settings_panel.preview_changed.connect(
                self._apply_settings_preview
            )
        self._settings_panel.show()
        self._settings_panel.raise_()
        self._settings_panel._update_voice_wake_ui()
        logger.debug("Settings panel opened")

    def _quit(self):
        """退出应用。"""
        logger.info("Application quitting...")
        self._voice_wake.stop()
        self._behavior_controller.stop()
        self._emotion_system.stop()
        self._memory.save()
        self._state_machine.transition_to("idle")
        self._tray.hide()
        QApplication.instance().quit()

    def _show_greeting(self):
        """显示问候语。"""
        if self._config.get("behavior.dialogue_enabled", True):
            text = self._dialogue_content.get_time_based_line()
            self._show_dialogue(text)

    def _show_dialogue(self, text: str):
        """在宠物头顶显示对话气泡。"""
        if not self._config.get("behavior.dialogue_enabled", True):
            return

        pet_x = self._window.pos().x()
        pet_y = self._window.pos().y()
        pet_w = self._window.width()

        self._dialogue_bubble.show_text(text, duration=3000)
        bubble_w = self._dialogue_bubble.width()
        bubble_x = pet_x + (pet_w - bubble_w) // 2
        bubble_y = pet_y - self._dialogue_bubble.height() - 5
        self._dialogue_bubble.move(bubble_x, bubble_y)
        self._dialogue_bubble.show()
        self._dialogue_bubble.raise_()

    def _update_bubble_position(self):
        """若气泡可见，重新定位"""
        if not self._dialogue_bubble.isVisible():
            return
        pet_x = self._window.pos().x()
        pet_y = self._window.pos().y()
        pet_w = self._window.width()
        bubble_w = self._dialogue_bubble.width()
        bubble_x = pet_x + (pet_w - bubble_w) // 2
        bubble_y = pet_y - self._dialogue_bubble.height() - 5
        self._dialogue_bubble.move(bubble_x, bubble_y)

    def _random_dialogue(self):
        """随机显示一句对话。"""
        if self._state_machine.is_state("sleep"):
            return
        if random.random() < 0.3:
            text = self._dialogue_content.get_idle_line()
            self._show_dialogue(text)

        # 重新设置随机间隔
        interval = random.randint(30000, 60000)
        self._dialogue_timer.start(interval)

    # ─── 事件回调 ───

    def _on_pet_click(self, data: dict):
        """处理单击宠物。"""
        # 记录互动
        self._memory.record_interaction()

        current = self._state_machine.current_state_name
        if current == "sleep":
            # 唤醒 → 情感变化 + 记录
            self._emotion_system.on_wake()
            self._memory.record_wake()
            if self._config.get("behavior.dialogue_enabled", True):
                text = self._dialogue_content.get_wake_line()
                self._show_dialogue(text)
        elif current != "dragged":
            # 点击 → 快乐↑ 依恋↑
            self._emotion_system.on_user_click()
            if self._config.get("behavior.dialogue_enabled", True):
                text = self._dialogue_content.get_click_line()
                self._show_dialogue(text)

    def _on_pet_double_click(self, data: dict):
        """处理双击宠物。"""
        current = self._state_machine.current_state_name
        if current not in ("sleep", "dragged"):
            anim = random.choice(["typing", "watching"])
            self._anim_manager.play(anim)
            if self._config.get("behavior.dialogue_enabled", True):
                text = self._dialogue_content.get_click_line()
                self._show_dialogue(text)

    def _on_pet_right_click(self, data: dict):
        """处理右键宠物。"""
        if self._state_machine.is_state("sleep"):
            return
        if self._config.get("behavior.dialogue_enabled", True):
            text = self._dialogue_content.get_hover_line()
            self._show_dialogue(text)

    def _on_hover_enter(self, data: dict):
        """鼠标悬停进入。"""
        if self._state_machine.is_state("sleep"):
            return
        # 悬停 → 好奇心小幅上升 + 记录互动
        self._emotion_system.on_user_hover()
        self._memory.record_interaction()
        if random.random() < 0.3:
            if self._config.get("behavior.dialogue_enabled", True):
                text = self._dialogue_content.get_hover_line()
                self._show_dialogue(text)

    def _on_hover_leave(self, data: dict):
        """鼠标悬停离开。"""
        pass

    def _on_window_mouse_pressed(self, data: dict):
        """窗口鼠标按下 → 检查是否为拖动开始。"""
        if not self._state_machine.is_state("dragged"):
            # 拖动 → 快乐小幅下降
            self._emotion_system.on_user_drag()
            self._behavior_controller.on_drag_start()

    def _on_state_changed(self, data: dict):
        """状态变化回调。"""
        new = data.get("to", "")

        # 非 sleep 状态：开启始终命令模式（直接说命令即可）
        if new != "sleep":
            self._voice_wake.set_command_mode(True)
        else:
            # sleep 状态：关闭命令模式，需要「嘿」唤醒
            self._voice_wake.set_command_mode(False)

    def _on_voice_wake(self, data: dict):
        """语音唤醒回调。"""
        # 显示唤醒回应
        if self._config.get("behavior.dialogue_enabled", True):
            text = self._dialogue_content.get_wake_line()
            self._show_dialogue(text)

        current = self._state_machine.current_state_name

        # 从 sleep 唤醒：进入 5 秒命令窗口
        if current == "wake":
            self._voice_wake.enter_command_mode()
            self._command_window_active = True
            self._command_window_timer.start(5000)
            logger.info("[Voice] Command window started (5s)")

    def _on_voice_command(self, data: dict):
        """语音命令回调。"""
        intent = data.get("intent", "unknown")
        logger.info("[Voice] Command received: %s", intent)

        if intent == Intent.TIME_QUERY.value:
            response = get_time_response()
            if self._config.get("behavior.dialogue_enabled", True):
                self._show_dialogue(response)

        elif intent == Intent.OPEN_BROWSER.value:
            success, response = open_browser()
            if self._config.get("behavior.dialogue_enabled", True):
                self._show_dialogue(response)

        # 如果在命令窗口期内，处理完命令后关闭窗口
        if self._command_window_active:
            self._end_command_window()

    def _on_command_window_timeout(self):
        """命令窗口超时 → 退出语音交互。"""
        logger.info("[Voice] Command window timeout")
        self._end_command_window()

    def _end_command_window(self):
        """退出命令窗口模式。"""
        if self._command_window_active:
            self._command_window_active = False
            self._command_window_timer.stop()
            self._voice_wake.exit_command_mode()
            logger.info("[Voice] Command window ended")

    def eventFilter(self, watched, event):
        """事件过滤器"""
        if watched is self._window and event.type() == QEvent.Move:
            self._update_bubble_position()
        return super().eventFilter(watched, event)
