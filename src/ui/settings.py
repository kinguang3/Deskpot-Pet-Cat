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
        self._config = ConfigManager()
        self._event_bus = EventBus()

        self._current = {}
        self._initial = {}
        self._dirty = False

        self.setWindowTitle("GBC Nina - 设置")
        self.setFixedSize(320, 400)
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

        # 更新标签显示
        self._size_label.setText(f"{self._size_slider.value()}%")
        self._opacity_label.setText(f"{self._opacity_slider.value()}%")

    def _save_settings(self):
        """保存当前临时设置到配置文件"""
        # 将 _current 写入 _config
        for key, value in self._current.items():
            self._config.set(key, value)
        self._config.save()

        # 更新初始备份，清除脏标记
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
