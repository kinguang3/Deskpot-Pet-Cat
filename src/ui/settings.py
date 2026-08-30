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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config = ConfigManager()
        self._event_bus = EventBus()

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

    def _load_settings(self):
        """从配置加载当前值。"""
        self._size_slider.setValue(
            int(self._config.get("window.size_scale", 1.0) * 100)
        )
        self._opacity_slider.setValue(
            int(self._config.get("window.opacity", 0.95) * 100)
        )
        self._topmost_check.setChecked(
            self._config.get("window.always_on_top", True)
        )
        self._auto_move_check.setChecked(
            self._config.get("behavior.auto_move", True)
        )
        self._dialogue_check.setChecked(
            self._config.get("behavior.dialogue_enabled", True)
        )

    def _save_settings(self):
        """保存设置到配置。"""
        self._config.set("window.size_scale", self._size_slider.value() / 100)
        self._config.set("window.opacity", self._opacity_slider.value() / 100)
        self._config.set(
            "window.always_on_top", self._topmost_check.isChecked()
        )
        self._config.set(
            "behavior.auto_move", self._auto_move_check.isChecked()
        )
        self._config.set(
            "behavior.dialogue_enabled", self._dialogue_check.isChecked()
        )
        self._config.save()

        self.settings_changed.emit()
        self._event_bus.emit("settings.changed", self._config.get_all())

    def _reset_settings(self):
        """重置为默认设置。"""
        self._size_slider.setValue(100)
        self._opacity_slider.setValue(95)
        self._topmost_check.setChecked(True)
        self._auto_move_check.setChecked(True)
        self._dialogue_check.setChecked(True)
