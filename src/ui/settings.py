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
    QMessageBox,
    QDialog,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QTimer

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SettingsPanel(QWidget):
    """设置面板窗口。"""

    settings_changed = Signal()
    preview_changed = Signal(dict)

    def __init__(self, voice_manager=None, custom_commands=None, parent=None):
        super().__init__(parent)
        self._voice_manager = voice_manager
        self._custom_commands = custom_commands
        if self._voice_manager:
            self._voice_manager.permission_changed.connect(
                self._on_permission_changed
            )
        self._updating = False

        self._config = ConfigManager()
        self._event_bus = EventBus()

        self._current = {}
        self._initial = {}
        self._dirty = False

        self.setWindowTitle("GBC Nina - 设置")
        self.setFixedSize(320, 520)
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self._setup_ui()
        self._load_settings()
        self._update_voice_wake_ui()
        self._refresh_custom_commands()
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

        self._voice_wake_check = QCheckBox("语音唤醒 (嘿，Nina)")
        behavior_layout.addWidget(self._voice_wake_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        # 自定义语音指令
        if self._custom_commands:
            custom_group = QGroupBox("自定义语音指令")
            custom_layout = QVBoxLayout()

            # 指令列表
            self._custom_list = QListWidget()
            self._custom_list.setMaximumHeight(100)
            custom_layout.addWidget(self._custom_list)

            # 操作按钮
            custom_btn_layout = QHBoxLayout()
            self._custom_add_btn = QPushButton("添加")
            self._custom_edit_btn = QPushButton("编辑")
            self._custom_del_btn = QPushButton("删除")
            self._custom_add_btn.clicked.connect(self._on_custom_add)
            self._custom_edit_btn.clicked.connect(self._on_custom_edit)
            self._custom_del_btn.clicked.connect(self._on_custom_del)
            custom_btn_layout.addWidget(self._custom_add_btn)
            custom_btn_layout.addWidget(self._custom_edit_btn)
            custom_btn_layout.addWidget(self._custom_del_btn)
            custom_layout.addLayout(custom_btn_layout)

            custom_group.setLayout(custom_layout)
            layout.addWidget(custom_group)

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
        self._voice_wake_check.stateChanged.connect(
            self._on_voice_wake_changed
        )

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

    def _on_voice_wake_changed(self, state):
        if self._updating:
            return
        if not self._voice_wake_check.isEnabled():
            # 如果控件被禁用，忽略点击
            return

        self._updating = True
        try:
            self._apply_preview("voice_wake.enabled", bool(state))
            if self._voice_manager:
                success = self._voice_manager.try_enable(bool(state))
                if not success and bool(state):
                    # 启动失败：禁用，取消勾选，弹窗
                    self._voice_wake_check.setEnabled(False)
                    self._voice_wake_check.blockSignals(True)
                    self._voice_wake_check.setChecked(False)
                    self._voice_wake_check.blockSignals(False)
                    QMessageBox.warning(
                        self,
                        "麦克风权限不足",
                        "无法启用语音唤醒，请检查麦克风连接和权限设置。",
                    )
                elif success and bool(state):
                    # 成功启用，确保控件可用
                    self._voice_wake_check.setEnabled(True)
                else:
                    self._apply_preview("voice_wake.enabled", False)
                    # 用户取消勾选，恢复控件可用
                    self._voice_wake_check.setEnabled(True)
        finally:
            self._updating = False

    def _on_permission_changed(self, available: bool):
        if self._updating:
            return
        if not available:
            # 如果当前配置是 True，则显示为禁用状态
            config_enabled = self._config.get("voice_wake.enabled", True)
            self._voice_wake_check.blockSignals(True)
            if config_enabled:
                self._voice_wake_check.setChecked(False)
                self._voice_wake_check.setEnabled(False)
            else:
                self._voice_wake_check.setChecked(False)
                self._voice_wake_check.setEnabled(True)
            self._voice_wake_check.blockSignals(False)
            self._apply_preview("voice_wake.enabled", config_enabled)
            logger.warning("Voice wake disabled due to permission loss")
        else:
            # 权限恢复时，刷新UI（可重新启用）
            self._update_voice_wake_ui()

    def _update_voice_wake_ui(self):
        """根据当前权限和配置更新复选框状态"""

        if not self._voice_manager:
            return
        has_perm = self._voice_manager.check_permission()
        # 读取配置
        config_enabled = self._config.get("voice_wake.enabled", True)

        self._voice_wake_check.blockSignals(True)
        if config_enabled and has_perm:
            self._voice_wake_check.setChecked(True)
            self._voice_wake_check.setEnabled(True)
        elif config_enabled and not has_perm:
            self._voice_wake_check.setChecked(False)
            self._voice_wake_check.setEnabled(False)
        else:
            self._voice_wake_check.setChecked(False)
            self._voice_wake_check.setEnabled(True)
        self._voice_wake_check.blockSignals(False)

    def _refresh_custom_commands(self):
        """刷新自定义指令列表。"""
        if not self._custom_commands:
            return
        self._custom_list.clear()
        for cmd in self._custom_commands.get_all():
            phrases_text = ", ".join(cmd.phrases)
            status = "✓" if cmd.enabled else "✗"
            label = f"{status} {phrases_text} → {cmd.action_type}:{cmd.action_target[:30]}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cmd.id)
            self._custom_list.addItem(item)

    def _on_custom_add(self):
        """添加自定义指令。"""
        dialog = CustomCommandDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cmd = dialog.get_command()
            ok, err = self._custom_commands.add(cmd)
            if not ok:
                QMessageBox.warning(self, "添加失败", err)
            else:
                self._refresh_custom_commands()

    def _on_custom_edit(self):
        """编辑自定义指令。"""
        current = self._custom_list.currentItem()
        if not current:
            return
        cmd_id = current.data(Qt.ItemDataRole.UserRole)
        all_cmds = self._custom_commands.get_all()
        cmd = next((c for c in all_cmds if c.id == cmd_id), None)
        if not cmd:
            return
        dialog = CustomCommandDialog(command=cmd, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.get_command()
            updated.id = cmd_id
            ok, err = self._custom_commands.update(updated)
            if not ok:
                QMessageBox.warning(self, "编辑失败", err)
            else:
                self._refresh_custom_commands()

    def _on_custom_del(self):
        """删除自定义指令。"""
        current = self._custom_list.currentItem()
        if not current:
            return
        cmd_id = current.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除这条语音指令吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._custom_commands.delete(cmd_id)
            self._refresh_custom_commands()

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
        self._voice_wake_check.setChecked(
            self._current.get("voice_wake.enabled", True)
        )

        # 更新标签显示
        self._size_label.setText(f"{self._size_slider.value()}%")
        self._opacity_label.setText(f"{self._opacity_slider.value()}%")

    def _save_settings(self):
        """保存当前临时设置到配置文件。"""
        # 只保存面板管理的 key，不覆盖 custom_voice_commands
        _PANEL_KEYS = (
            "window.size_scale", "window.opacity", "window.always_on_top",
            "behavior.auto_move", "behavior.dialogue_enabled",
            "voice_wake.enabled",
        )
        for key in _PANEL_KEYS:
            if key in self._current:
                self._config.set(key, self._current[key])
        self._config.save()

        # 同步 custom_voice_commands（由 CustomCommandManager 直接管理）
        if self._custom_commands:
            data = [cmd.to_dict() for cmd in self._custom_commands.get_all()]
            self._config.set("custom_voice_commands", data)
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


class CustomCommandDialog(QDialog):
    """自定义语音指令编辑对话框。"""

    def __init__(self, command=None, parent=None):
        super().__init__(parent)
        self._command = command
        self._is_edit = command is not None

        self.setWindowTitle("编辑指令" if self._is_edit else "添加指令")
        self.setFixedSize(300, 280)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 触发语句
        layout.addWidget(QLabel("触发语句（逗号分隔）:"))
        self._phrases_edit = QLineEdit()
        self._phrases_edit.setPlaceholderText("例如: 打开百度,百度搜索")
        layout.addWidget(self._phrases_edit)

        # 动作类型
        layout.addWidget(QLabel("动作类型:"))
        self._action_combo = QComboBox()
        self._action_combo.addItem("打开网页", "open_url")
        self._action_combo.addItem("打开应用", "open_app")
        layout.addWidget(self._action_combo)

        # 动作目标
        layout.addWidget(QLabel("动作目标:"))
        self._target_edit = QLineEdit()
        self._target_edit.setPlaceholderText("例如: https://www.baidu.com")
        layout.addWidget(self._target_edit)

        # 回复语句
        layout.addWidget(QLabel("回复语句（可选）:"))
        self._response_edit = QLineEdit()
        self._response_edit.setPlaceholderText("留空则使用默认回复")
        layout.addWidget(self._response_edit)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # 填充编辑模式数据
        if self._is_edit:
            self._phrases_edit.setText(", ".join(command.phrases))
            idx = self._action_combo.findData(command.action_type)
            if idx >= 0:
                self._action_combo.setCurrentIndex(idx)
            self._target_edit.setText(command.action_target)
            self._response_edit.setText(command.response)

    def _validate_and_accept(self):
        """验证输入后关闭。"""
        phrases_text = self._phrases_edit.text().strip()
        if not phrases_text:
            QMessageBox.warning(self, "输入错误", "触发语句不能为空")
            return

        target = self._target_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "输入错误", "动作目标不能为空")
            return

        action_type = self._action_combo.currentData()
        if action_type == "open_url":
            if not target.startswith(("http://", "https://")):
                QMessageBox.warning(self, "输入错误", "链接必须以 http:// 或 https:// 开头")
                return

        self.accept()

    def get_command(self):
        """获取编辑后的指令。"""
        from src.voice.custom_commands import CustomCommand

        phrases_text = self._phrases_edit.text().strip()
        phrases = [p.strip() for p in phrases_text.split(",") if p.strip()]

        return CustomCommand(
            phrases=phrases,
            action_type=self._action_combo.currentData(),
            action_target=self._target_edit.text().strip(),
            response=self._response_edit.text().strip(),
            enabled=True if not self._is_edit else self._command.enabled,
        )
