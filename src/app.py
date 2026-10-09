# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""应用管理器模块

负责初始化和协调所有模块。
管理应用生命周期。
"""

import os
import random
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, QObject, QEvent

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
from src.behavior.mover import WalkMover
from src.behavior.emotion import EmotionSystem
from src.behavior.memory import Memory

from src.interaction.mouse import MouseInteraction
from src.dialogue.bubble import DialogueBubble
from src.dialogue.content import DialogueContent
from src.ui.tray import SystemTray
from src.ui.settings import SettingsPanel
from src.ui.privacy_dialog import PrivacyDialog, VoiceOptInDialog
from src.utils.storage import Storage
from src.utils.logger import get_logger
from src.voice import VoiceManager

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

        # 自主行走位移（把 walk 状态真正落到窗口坐标上）
        self._walk_mover = WalkMover(self._pet, self._window)

        # 情感系统（管理内部状态，影响行为权重）
        self._emotion_system = EmotionSystem(
            self._behavior_controller.scheduler
        )

        # 记忆系统（持久化互动数据）
        self._memory = Memory(self._storage)

        # 语音情绪管理（AssemblyAI）
        self._voice_manager = VoiceManager()

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
        self._tray.privacy_requested.connect(self._show_privacy)
        self._tray.quit_requested.connect(self._quit)

        # 交互事件
        self._event_bus.on("interaction.single_click", self._on_pet_click)
        self._event_bus.on(
            "interaction.double_click", self._on_pet_double_click
        )
        self._event_bus.on("interaction.right_click", self._on_pet_right_click)
        self._event_bus.on("interaction.hover_enter", self._on_hover_enter)
        self._event_bus.on("interaction.hover_leave", self._on_hover_leave)

        # 窗口拖动事件（mouse_moved 仅在拖动时发射，mouse_pressed 每次点击都发射）
        self._event_bus.on(
            "window.mouse_moved", self._on_window_mouse_moved
        )

        # 状态变化事件
        self._event_bus.on("state.changed", self._on_state_changed)

        # 语音情绪事件
        self._event_bus.on("voice.emotion_detected", self._on_voice_emotion)

        # 设置变更（保存后热重载语音指令）
        self._event_bus.on("settings.changed", self._on_settings_changed)

        # 语音指令事件
        self._event_bus.on("voice.command_detected", self._on_voice_command)
        self._event_bus.on("command.show_dialogue", self._on_command_show_dialogue)
        self._event_bus.on("command.play_animation", self._on_command_play_animation)
        self._event_bus.on("command.show_status", self._on_command_show_status)
        self._event_bus.on("command.open_website", self._on_command_open_website)

    def start(self):
        """启动应用。"""
        logger.info("Application starting...")

        # 首次运行必须先过隐私协议，否则不启动任何东西（含麦克风）
        if not self._ensure_privacy_consent():
            logger.info("User declined privacy agreement, exiting")
            return False

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

        # 启动语音情绪管理（可选，失败不影响主程序）
        voice_ok = self._voice_manager.start()
        if voice_ok:
            logger.info("VoiceManager started")
        else:
            logger.info("VoiceManager not started (disabled or unavailable)")

        # 显示问候语
        QTimer.singleShot(1000, self._show_greeting)

        logger.info("Application started")
        return True

    # ─── 隐私协议 / 首次运行 ───

    def _ensure_privacy_consent(self) -> bool:
        """确保用户已同意隐私协议。首次运行时弹窗征询。

        返回 False 表示用户不同意，应用应当直接退出。
        已同意过的用户不再打扰（同意状态落盘到 config/user.json）。
        """
        if self._config.get("app.privacy_accepted", False):
            return True

        logger.info("First run: showing privacy agreement")
        dlg = PrivacyDialog()
        if dlg.exec() != PrivacyDialog.DialogCode.Accepted:
            logger.info("Privacy agreement declined")
            return False
        # exec() 返回 Accepted 也要确认勾选确实打上了
        if not dlg.is_accepted:
            logger.info("Privacy agreement not checked, treating as declined")
            return False

        # 语音单独征询，默认不开启麦克风
        voice_opt = VoiceOptInDialog()
        wants_voice = voice_opt.exec() == VoiceOptInDialog.DialogCode.Accepted

        self._config.set("app.privacy_accepted", True)
        self._config.set("app.first_run_completed", True)
        self._config.set("voice.enabled", bool(wants_voice))

        if not self._config.save():
            # 落盘失败会导致下次启动又弹协议，必须让用户知道
            logger.error(
                "Failed to persist privacy consent; "
                "agreement will be requested again on next start"
            )
            QMessageBox.warning(
                None,
                "无法保存设置",
                "隐私协议同意状态保存失败（程序目录可能不可写）。\n"
                "本次仍可继续使用，但下次启动会再次询问。",
            )
        else:
            logger.info(
                "Privacy consent recorded (voice_enabled=%s)", wants_voice
            )
        return True

    def _apply_config(self):
        """应用配置到各个模块。"""
        scale = self._config.get("window.size_scale", 1.0)
        self._window.set_scale(scale)

        opacity = self._config.get("window.opacity", 0.95)
        self._window.set_opacity(opacity)

        # 置顶状态必须在这里应用，否则用户保存后重启就丢失
        self._window.set_always_on_top(
            self._config.get("window.always_on_top", True)
        )

    def _apply_settings_preview(self, settings: dict):
        """根据预览设置实时更新桌宠窗口"""
        # 大小缩放
        scale = settings.get("window.size_scale", 1.0)
        self._window.set_scale(scale)
        # 透明度
        opacity = settings.get("window.opacity", 0.95)
        self._window.setWindowOpacity(opacity)
        # 置顶
        self._window.set_always_on_top(
            settings.get("window.always_on_top", True)
        )

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
            self._settings_panel = SettingsPanel()
            self._settings_panel.settings_changed.connect(self._apply_config)
            self._settings_panel.preview_changed.connect(
                self._apply_settings_preview
            )
        self._settings_panel.show()
        self._settings_panel.raise_()
        logger.debug("Settings panel opened")

    def _show_privacy(self):
        """从托盘查看隐私协议（只读，不改同意状态）。"""
        dlg = PrivacyDialog()
        dlg._accept_btn.setVisible(False)
        dlg._agree_check.setVisible(False)
        dlg._exit_btn.setText("关闭")
        dlg.exec()

    def _quit(self):
        """退出应用。"""
        logger.info("Application quitting...")
        quiesced = self._voice_manager.stop()
        self._behavior_controller.stop()
        self._walk_mover.stop()
        self._emotion_system.stop()
        self._memory.save()
        self._state_machine.transition_to("idle")
        self._tray.hide()
        QApplication.instance().quit()

        if not quiesced:
            # 仍有分析任务卡在不可中断的 I/O 上（典型是云端转录）。
            # concurrent.futures 在解释器退出时会 join 这些线程，最坏等到
            # provider 超时（60s），表现为"点了退出但进程半天不消失"。
            # 此时直接结束进程：记忆与配置已同步落盘，本地推理子进程已由
            # provider.close() 终止，不会残留孤儿进程。
            logger.warning(
                "仍有语音任务未结束，跳过线程等待并直接结束进程"
            )
            os._exit(0)

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

    def _on_window_mouse_moved(self, data: dict):
        """窗口拖动开始 → 进入 dragged 状态。"""
        if self._state_machine.is_state("dragged"):
            return
        self._emotion_system.on_user_drag()
        self._behavior_controller.on_drag_start()

    def _on_state_changed(self, data: dict):
        """状态变化回调。

        其他模块（BehaviorController / EmotionSystem）各自监听该事件，
        这里只保留订阅占位，避免误删注册关系。
        """
        return

    def _on_voice_emotion(self, data: dict):
        """处理语音情绪检测结果。"""
        emotion = data.get("emotion", "NEUTRAL")
        sentiment = data.get("sentiment", "NEUTRAL")
        energy = data.get("energy", 0.0)
        text = data.get("text", "")
        is_listening = data.get("is_listening", False)

        # 影响内部情感系统（长期）
        self._emotion_system.on_voice_emotion(emotion, sentiment, energy)

        # 如果在聆听模式，显示聆听状态
        if is_listening:
            if self._config.get("behavior.dialogue_enabled", True):
                self._show_dialogue("我在听...")
            return

        # 显示反应台词（短期）
        if self._config.get("behavior.dialogue_enabled", True):
            reaction = self._dialogue_content.get_voice_emotion_line(emotion)
            self._show_dialogue(reaction)

        logger.info(
            "Voice emotion reacted: %s (energy=%.1f) -> %s",
            emotion,
            energy,
            reaction if self._config.get("behavior.dialogue_enabled", True) else "no dialogue",
        )

    def _on_voice_command(self, data: dict):
        """处理语音指令检测结果。"""
        action = data.get("action", "")
        text = data.get("text", "")

        logger.info("Voice command detected: action=%s, text=%s", action, text)

    def _on_settings_changed(self, data: dict):
        """设置保存后热重载语音指令。"""
        self._voice_manager.get_command_manager().reload()

    def _on_command_show_dialogue(self, data: dict):
        """显示指令对话。"""
        text = data.get("text", "")
        if text and self._config.get("behavior.dialogue_enabled", True):
            self._show_dialogue(text)

    def _on_command_play_animation(self, data: dict):
        """播放指令动画。"""
        animation = data.get("animation", "")
        if not animation:
            return

        # happy/dance 无独立帧资源，映射到现有状态与动画
        if animation == "happy":
            self._state_machine.transition_to("happy")
            return
        if animation == "dance":
            logger.warning("No dance animation sprite, fallback to happy state")
            self._state_machine.transition_to("happy")
            return

        self._anim_manager.play(animation)

    def _on_command_show_status(self, data: dict):
        """显示状态信息。"""
        if self._config.get("behavior.dialogue_enabled", True):
            # 获取情感状态
            emotion_info = self._emotion_system.get_debug_info()
            status_text = (
                f"精力: {emotion_info['energy']:.0f} "
                f"快乐: {emotion_info['happiness']:.0f} "
                f"好奇: {emotion_info['curiosity']:.0f}"
            )
            self._show_dialogue(status_text)

    def _on_command_open_website(self, data: dict):
        """打开网站。"""
        url = data.get("url", "")
        if url:
            import webbrowser
            try:
                webbrowser.open(url)
                logger.info("Opened website: %s", url)
                if self._config.get("behavior.dialogue_enabled", True):
                    self._show_dialogue(f"正在打开 {url}")
            except Exception as e:
                logger.exception("Failed to open website: %s", url)
                if self._config.get("behavior.dialogue_enabled", True):
                    self._show_dialogue("打开网站失败")

    def eventFilter(self, watched, event):
        """事件过滤器"""
        if watched is self._window and event.type() == QEvent.Move:
            self._update_bubble_position()
        return super().eventFilter(watched, event)
