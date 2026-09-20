# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""设置面板模块

提供设置界面，让用户配置桌宠行为。
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QCheckBox,
    QPushButton,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QComboBox,
    QInputDialog,
)
from PySide6.QtCore import Qt, Signal

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SettingsPanel(QWidget):
    """设置面板窗口。"""

    settings_changed = Signal()
    preview_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False

        self._config = ConfigManager()
        self._event_bus = EventBus()

        self._current = {}
        self._initial = {}
        self._dirty = False

        self.setWindowTitle("GBC Nina - 设置")
        self.setFixedSize(350, 550)
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self._setup_ui()
        self._load_settings()
        logger.debug("SettingsPanel created")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 窗口设置
        window_group = QGroupBox("窗口")
        window_layout = QVBoxLayout()

        # 大小缩放
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("大小"))
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(50, 200)
        self._size_slider.setTickInterval(10)
        self._size_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        size_layout.addWidget(self._size_slider)
        self._size_label = QLabel("100%")
        self._size_label.setFixedWidth(40)
        size_layout.addWidget(self._size_label)
        window_layout.addLayout(size_layout)

        # 透明度
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("透明度"))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(30, 100)
        self._opacity_slider.setTickInterval(10)
        self._opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        opacity_layout.addWidget(self._opacity_slider)
        self._opacity_label = QLabel("95%")
        self._opacity_label.setFixedWidth(40)
        opacity_layout.addWidget(self._opacity_label)
        window_layout.addLayout(opacity_layout)

        # 置顶
        self._topmost_check = QCheckBox("始终置顶")
        window_layout.addWidget(self._topmost_check)

        window_group.setLayout(window_layout)
        layout.addWidget(window_group)

        # 行为设置
        behavior_group = QGroupBox("行为")
        behavior_layout = QVBoxLayout()

        self._auto_move_check = QCheckBox("自动移动")
        behavior_layout.addWidget(self._auto_move_check)

        self._dialogue_check = QCheckBox("显示对话")
        behavior_layout.addWidget(self._dialogue_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        # 语音指令设置
        commands_group = QGroupBox("语音指令")
        commands_layout = QVBoxLayout()

        # 唤醒词
        wake_layout = QHBoxLayout()
        wake_layout.addWidget(QLabel("唤醒词:"))
        self._wake_words_input = QLineEdit()
        self._wake_words_input.setPlaceholderText("用逗号分隔，如: hey nina, 小猫")
        wake_layout.addWidget(self._wake_words_input)
        commands_layout.addLayout(wake_layout)

        # 指令列表
        self._commands_list = QListWidget()
        self._commands_list.setMaximumHeight(120)
        commands_layout.addWidget(self._commands_list)

        # 指令操作按钮
        cmd_btn_layout = QHBoxLayout()

        self._add_cmd_btn = QPushButton("添加")
        self._add_cmd_btn.clicked.connect(self._add_command)
        cmd_btn_layout.addWidget(self._add_cmd_btn)

        self._edit_cmd_btn = QPushButton("编辑")
        self._edit_cmd_btn.clicked.connect(self._edit_command)
        cmd_btn_layout.addWidget(self._edit_cmd_btn)

        self._delete_cmd_btn = QPushButton("删除")
        self._delete_cmd_btn.clicked.connect(self._delete_command)
        cmd_btn_layout.addWidget(self._delete_cmd_btn)

        commands_layout.addLayout(cmd_btn_layout)

        commands_group.setLayout(commands_layout)
        layout.addWidget(commands_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self._save_settings)
        self._reset_btn = QPushButton("重置")
        self._reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._reset_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

        # 连接信号
        self._size_slider.valueChanged.connect(
            lambda v: self._size_label.setText(f"{v}%")
        )
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )

        self._size_slider.valueChanged.connect(self._on_size_changed)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self._topmost_check.stateChanged.connect(self._on_topmost_changed)
        self._auto_move_check.stateChanged.connect(self._on_auto_move_changed)
        self._dialogue_check.stateChanged.connect(self._on_dialogue_changed)

    def _on_size_changed(self, val):
        self._size_label.setText(f"{val}%")
        self._apply_preview("window.size_scale", val / 100)

    def _on_opacity_changed(self, val):
        self._opacity_label.setText(f"{val}%")
        self._apply_preview("window.opacity", val / 100)

    def _on_topmost_changed(self, state):
        self._apply_preview("window.always_on_top", bool(state))

    def _on_auto_move_changed(self, state):
        self._apply_preview("behavior.auto_move", bool(state))

    def _on_dialogue_changed(self, state):
        self._apply_preview("behavior.dialogue_enabled", bool(state))

    def _add_command(self):
        """添加新指令。"""
        trigger, ok = QInputDialog.getText(
            self, "添加指令", "触发词:", QLineEdit.EchoMode.Normal
        )
        if not ok or not trigger:
            return

        # 选择动作
        actions = [
            ("show_time", "显示时间"),
            ("show_date", "显示日期"),
            ("show_greeting", "显示问候语"),
            ("play_happy", "播放开心动画"),
            ("play_dance", "播放跳舞动画"),
            ("show_status", "显示状态"),
            ("show_dialogue", "显示自定义对话"),
            ("open_website", "打开网站"),
        ]

        action, ok = QInputDialog.getItem(
            self, "选择动作", "动作:", [f"{a[0]} - {a[1]}" for a in actions], 0, False
        )
        if not ok:
            return

        action_key = action.split(" - ")[0]

        # 如果是 show_dialogue，获取自定义文本
        custom_text = ""
        if action_key == "show_dialogue":
            custom_text, ok = QInputDialog.getText(
                self, "自定义对话", "显示文本:", QLineEdit.EchoMode.Normal
            )
            if not ok:
                return

        # 如果是 open_website，获取网址
        custom_url = ""
        if action_key == "open_website":
            custom_url, ok = QInputDialog.getText(
                self, "打开网站", "网址:", QLineEdit.EchoMode.Normal,
                placeholderText="example.com"
            )
            if not ok or not custom_url:
                return

        # 添加到配置
        commands = self._current.get("voice.commands.custom", [])
        cmd = {
            "trigger": trigger,
            "action": action_key,
            "description": custom_text or custom_url or action.split(" - ")[1],
        }
        if custom_text:
            cmd["custom_text"] = custom_text
        if custom_url:
            cmd["custom_url"] = custom_url
        commands.append(cmd)
        self._current["voice.commands.custom"] = commands

        # 更新列表
        self._refresh_commands_list()
        self._dirty = True

    def _edit_command(self):
        """编辑选中的指令。"""
        row = self._commands_list.currentRow()
        if row < 0:
            return

        commands = self._current.get("voice.commands.custom", [])
        if row >= len(commands):
            return

        cmd = commands[row]

        # 编辑触发词
        trigger, ok = QInputDialog.getText(
            self, "编辑指令", "触发词:", QLineEdit.EchoMode.Normal, cmd["trigger"]
        )
        if not ok or not trigger:
            return

        cmd["trigger"] = trigger
        self._current["voice.commands.custom"] = commands

        # 更新列表
        self._refresh_commands_list()
        self._dirty = True

    def _delete_command(self):
        """删除选中的指令。"""
        row = self._commands_list.currentRow()
        if row < 0:
            return

        commands = self._current.get("voice.commands.custom", [])
        if row >= len(commands):
            return

        cmd = commands.pop(row)
        self._current["voice.commands.custom"] = commands

        # 更新列表
        self._refresh_commands_list()
        self._dirty = True

    def _refresh_commands_list(self):
        """刷新指令列表显示。"""
        self._commands_list.clear()
        commands = self._current.get("voice.commands.custom", [])
        for cmd in commands:
            trigger = cmd.get("trigger", "")
            action = cmd.get("action", "")
            if action == "open_website":
                url = cmd.get("custom_url", "")
                self._commands_list.addItem(f"{trigger} -> 打开 {url}")
            elif action == "show_dialogue":
                text = cmd.get("custom_text", "")
                self._commands_list.addItem(f"{trigger} -> 说 '{text}'")
            else:
                self._commands_list.addItem(f"{trigger} -> {action}")

    def _apply_preview(self, key, value):
        """更新临时配置，发出预览信号，"""
        self._current[key] = value
        self._dirty = True
        self.preview_changed.emit(self._current.copy())

    def _load_settings(self):
        """从配置文件加载，初始化临时和初始状态"""
        # 读取当前配置
        self._current = self._config.get_all().copy()
        self._initial = self._current.copy()

        # 更新UI控件
        self._size_slider.setValue(
            int(self._current.get("window.size_scale", 1.0) * 100)
        )
        self._opacity_slider.setValue(
            int(self._current.get("window.opacity", 0.95) * 100)
        )
        self._topmost_check.setChecked(
            self._current.get("window.always_on_top", True)
        )
        self._auto_move_check.setChecked(
            self._current.get("behavior.auto_move", True)
        )
        self._dialogue_check.setChecked(
            self._current.get("behavior.dialogue_enabled", True)
        )

        # 加载唤醒词
        wake_words = self._current.get("voice.commands.wake_words", ["hey nina", "小猫", "nina"])
        self._wake_words_input.setText(", ".join(wake_words))

        # 加载指令列表
        self._refresh_commands_list()

        # 更新标签显示
        self._size_label.setText(f"{self._size_slider.value()}%")
        self._opacity_label.setText(f"{self._opacity_slider.value()}%")

    def _save_settings(self):
        """保存当前临时设置到配置文件。"""
        # 只保存面板管理的 key
        _PANEL_KEYS = (
            "window.size_scale",
            "window.opacity",
            "window.always_on_top",
            "behavior.auto_move",
            "behavior.dialogue_enabled",
        )
        for key in _PANEL_KEYS:
            if key in self._current:
                self._config.set(key, self._current[key])

        # 保存唤醒词
        wake_text = self._wake_words_input.text()
        wake_words = [w.strip() for w in wake_text.split(",") if w.strip()]
        self._config.set("voice.commands.wake_words", wake_words)

        # 保存自定义指令
        commands = self._current.get("voice.commands.custom", [])
        self._config.set("voice.commands.custom", commands)

        self._config.save()

        self._initial = self._current.copy()
        self._dirty = False

        self.settings_changed.emit()
        self._event_bus.emit("settings.changed", self._current.copy())

    def _reset_settings(self):
        """重置为默认值（硬编码，也可从配置文件默认读取）"""
        # 定义默认值（应与 ConfigManager 默认一致）
        defaults = {
            "window.size_scale": 1.0,
            "window.opacity": 0.95,
            "window.always_on_top": True,
            "behavior.auto_move": True,
            "behavior.dialogue_enabled": True,
            "voice.commands.wake_words": ["hey nina", "小猫", "nina"],
            "voice.commands.custom": [],
        }
        # 更新 _current 为默认值
        for key, val in defaults.items():
            self._current[key] = val

        # 更新UI控件
        self._size_slider.setValue(int(defaults["window.size_scale"] * 100))
        self._opacity_slider.setValue(int(defaults["window.opacity"] * 100))
        self._topmost_check.setChecked(defaults["window.always_on_top"])
        self._auto_move_check.setChecked(defaults["behavior.auto_move"])
        self._dialogue_check.setChecked(defaults["behavior.dialogue_enabled"])

        # 重置唤醒词和指令
        self._wake_words_input.setText(", ".join(defaults["voice.commands.wake_words"]))
        self._refresh_commands_list()

        self._size_label.setText(f"{self._size_slider.value()}%")
        self._opacity_label.setText(f"{self._opacity_slider.value()}%")

        # 应用预览（不保存）
        self.preview_changed.emit(self._current.copy())
        self._dirty = True

    def closeEvent(self, event):
        """关闭窗口时，如果未保存则恢复初始设置"""
        if self._dirty:
            # 恢复到打开时的状态
            self._current = self._initial.copy()
            # 更新UI控件以反映恢复值
            self._size_slider.setValue(
                int(self._current.get("window.size_scale", 1.0) * 100)
            )
            self._opacity_slider.setValue(
                int(self._current.get("window.opacity", 0.95) * 100)
            )
            self._topmost_check.setChecked(
                self._current.get("window.always_on_top", True)
            )
            self._auto_move_check.setChecked(
                self._current.get("behavior.auto_move", True)
            )
            self._dialogue_check.setChecked(
                self._current.get("behavior.dialogue_enabled", True)
            )
            self._size_label.setText(f"{self._size_slider.value()}%")
            self._opacity_label.setText(f"{self._opacity_slider.value()}%")
            # 通知主窗口恢复
            self.preview_changed.emit(self._current.copy())
            self._dirty = False

        event.accept()
