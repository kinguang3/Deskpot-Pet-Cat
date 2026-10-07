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
    QDialog,
    QDialogButtonBox,
    QScrollArea,
    QMessageBox,
    QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal

from src.core.config import ConfigManager
from src.core.event_bus import EventBus
from src.ui.privacy_dialog import PrivacyDialog
from src.utils.logger import get_logger
from src.voice.audio_capture import input_devices, resolve_input_device

logger = get_logger(__name__)


class MicLevelMonitor(QThread):
    """实时监测麦克风输入电平（0~100，近似 dBFS 映射）。

    点击「测试麦克风」时独立开路采集，不依赖正在运行的语音模块。
    多声道设备自动下混为单声道再算电平，与主采集逻辑一致。
    """

    level_changed = Signal(int, int)  # (percent, rms)

    def __init__(self, device=None, parent=None):
        super().__init__(parent)
        self._device = device
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice not installed for mic level monitor")
            return

        channels = 1
        device = self._device
        if device is not None:
            try:
                info = sd.query_devices(device)
                if int(info.get("max_input_channels") or 1) > 1:
                    channels = min(int(info["max_input_channels"]), 8)
            except Exception:
                channels = 1

        stream = None
        store = []

        def cb(indata, frames, time_info, status):
            try:
                # RawInputStream 的 indata 是 raw buffer，不是 numpy 数组
                a = np.frombuffer(indata, dtype=np.int16).astype(np.int32)
                ch = a.size // frames
                if ch > 1:
                    usable = a.size - (a.size % ch)
                    a = a[:usable].reshape(-1, ch).mean(axis=1)
                rms = float(np.sqrt(np.mean(a.astype(np.float32) ** 2)))
                store.append(rms)
            except Exception:
                pass

        try:
            stream = sd.RawInputStream(
                samplerate=16000, blocksize=1600, dtype="int16",
                channels=channels, device=device, callback=cb,
            )
            stream.start()
            while not self._stop:
                self.msleep(200)
                if store:
                    # 取窗口内峰值，语音瞬时电平才有显示意义
                    peak = max(store)
                    store.clear()
                    db = 20.0 * np.log10((peak + 1.0) / 32767.0)
                    percent = int(max(0.0, min(100.0, (db + 60.0) / 60.0 * 100.0)))
                    self.level_changed.emit(percent, int(peak))
        except Exception:
            logger.exception("Mic level monitor failed")
            self.level_changed.emit(-1, 0)
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass


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
        # 语音区新增了开关/Key/协议按钮等内容，固定尺寸会被裁掉，
        # 改为可缩放 + 内部滚动
        self.setMinimumSize(380, 480)
        self.resize(400, 680)
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self._setup_ui()
        self._load_settings()
        logger.debug("SettingsPanel created")

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # 内容放进滚动区，窗口缩小时不会把语音区控件裁掉
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
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

        # 语音总开关：默认关闭（麦克风不采集），需用户主动开启
        self._voice_enabled_check = QCheckBox("开启语音功能（使用麦克风）")
        self._voice_enabled_check.setToolTip(
            "开启后 Nina 会使用麦克风。\n"
            "本地引擎不可用时，语音片段可能上传至 AssemblyAI 云端。\n"
            "详见「隐私协议」。"
        )
        self._voice_enabled_check.stateChanged.connect(
            self._on_voice_enabled_changed
        )
        commands_layout.addWidget(self._voice_enabled_check)

        privacy_row = QHBoxLayout()
        privacy_hint = QLabel("语音默认关闭。")
        privacy_hint.setStyleSheet("color: #888; font-size: 11px;")
        privacy_row.addWidget(privacy_hint)
        privacy_row.addStretch()
        self._privacy_btn = QPushButton("查看隐私协议")
        self._privacy_btn.clicked.connect(self._show_privacy)
        privacy_row.addWidget(self._privacy_btn)
        commands_layout.addLayout(privacy_row)

        # AssemblyAI API Key：语音默认关闭，用户需自行填 Key 才能用云端
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("云端 Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText(
            "留空则无法使用云端转写（可只用本地引擎）"
        )
        key_layout.addWidget(self._api_key_input)
        commands_layout.addLayout(key_layout)

        # 唤醒词
        wake_layout = QHBoxLayout()
        wake_layout.addWidget(QLabel("唤醒词:"))
        self._wake_words_input = QLineEdit()
        self._wake_words_input.setPlaceholderText("用逗号分隔，如: hey nina, 小猫")
        wake_layout.addWidget(self._wake_words_input)
        commands_layout.addLayout(wake_layout)

        # 麦克风选择 + 实时电平（防「选了麦还是没声音」的无提示状态）
        mic_row = QHBoxLayout()
        mic_row.addWidget(QLabel("麦克风:"))
        self._mic_combo = QComboBox()
        self._mic_combo.setMinimumWidth(220)
        mic_row.addWidget(self._mic_combo, 1)
        self._mic_test_btn = QPushButton("测试")
        self._mic_test_btn.setCheckable(True)
        self._mic_test_btn.clicked.connect(self._on_toggle_mic_monitor)
        mic_row.addWidget(self._mic_test_btn)
        commands_layout.addLayout(mic_row)

        level_row = QHBoxLayout()
        self._mic_level_bar = QProgressBar()
        self._mic_level_bar.setRange(0, 100)
        self._mic_level_bar.setMaximumHeight(14)
        self._mic_level_bar.setTextVisible(False)
        level_row.addWidget(self._mic_level_bar, 1)
        self._mic_level_label = QLabel("")
        self._mic_level_label.setStyleSheet("color: #888; font-size: 11px;")
        level_row.addWidget(self._mic_level_label)
        commands_layout.addLayout(level_row)
        self._mic_monitor = None

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

    def _on_voice_enabled_changed(self, state):
        """语音总开关。麦克风开闭影响较大，打开时再确认一次。"""
        enabled = bool(state)
        if enabled:
            reply = QMessageBox.question(
                self,
                "开启语音功能",
                "开启后 Nina 会使用麦克风收集语音。\n\n"
                "本地引擎不可用时，语音片段可能上传至 AssemblyAI "
                "云端进行转写。\n\n"
                "确定要开启吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                # 用户反悔，撤销勾选（blocked 信号避免递归触发）
                self._voice_enabled_check.blockSignals(True)
                self._voice_enabled_check.setChecked(False)
                self._voice_enabled_check.blockSignals(False)
                return
        self._apply_preview("voice.enabled", enabled)

    def _show_privacy(self):
        """重新查看隐私协议（只读展示，不改同意状态）。"""
        dlg = PrivacyDialog(self)
        # 同意按钮在这里没有意义，直接隐藏避免误解
        dlg._accept_btn.setVisible(False)
        dlg._agree_check.setVisible(False)
        dlg._exit_btn.setText("关闭")
        dlg.exec()

    def _refresh_mic_devices(self, selected: str = ""):
        """填充麦克风下拉框；selected 为当前配置的设备名。"""
        self._mic_combo.clear()
        self._mic_combo.addItem("(系统默认)", "")
        for dev in input_devices():
            label = "%s (%dch)" % (dev["name"], dev["channels"])
            self._mic_combo.addItem(label, dev["name"])

        # 配置里存的设备不在当前列表时也补一项，保存后不会悄悄丢配置
        if selected and not any(
            self._mic_combo.itemData(i) == selected
            for i in range(self._mic_combo.count())
        ):
            self._mic_combo.addItem("%s (未找到)" % selected, selected)

        idx = self._mic_combo.findData(selected)
        self._mic_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_toggle_mic_monitor(self, checked: bool):
        """测试麦克风电平：开监听线程 / 停线程。"""
        if checked:
            self._stop_mic_monitor()
            device_name = self._mic_combo.currentData()
            device = resolve_input_device(device_name)
            self._mic_monitor = MicLevelMonitor(device=device, parent=self)
            self._mic_monitor.level_changed.connect(self._on_mic_level)
            self._mic_monitor.finished.connect(
                lambda: self._on_mic_monitor_done()
            )
            self._mic_level_bar.setValue(0)
            self._mic_level_label.setText("监听中…")
            self._mic_monitor.start()
        else:
            self._stop_mic_monitor()

    def _on_mic_level(self, percent: int, rms: int):
        if percent < 0:
            self._mic_level_label.setText("无法打开麦克风")
            return
        self._mic_level_bar.setValue(percent)
        if rms >= 400:
            self._mic_level_label.setText("电平: %d%% (有声音)" % percent)
        else:
            self._mic_level_label.setText("电平: %d%% (静音)" % percent)

    def _on_mic_monitor_done(self):
        if self._mic_test_btn.isChecked():
            self._mic_test_btn.setChecked(False)
        self._mic_monitor = None

    def _stop_mic_monitor(self):
        if self._mic_monitor is not None:
            monitor = self._mic_monitor
            monitor.stop()
            # 监听循环每 200ms 检查一次停止标志，正常很快退出
            monitor.wait(2000)
            self._mic_monitor = None

    def _add_command(self):
        """添加新指令。使用单个表单对话框，避免多步弹窗导致漏选动作。"""
        dlg = _CommandDialog(self, title="添加指令")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        trigger = dlg.trigger_text()
        action_key = dlg.action_key()
        custom_text = dlg.custom_text()
        custom_url = dlg.custom_url()

        # 添加到配置
        commands = self._current.get("voice.commands.custom", [])
        action_label = dict(_CommandDialog.ACTIONS).get(action_key, action_key)
        cmd = {
            "trigger": trigger,
            "action": action_key,
            "description": custom_text or custom_url or action_label,
            "match_type": dlg.match_type(),
            "require_wake_word": dlg.require_wake_word(),
        }
        if custom_text:
            cmd["custom_text"] = custom_text
        if custom_url:
            cmd["custom_url"] = custom_url
        commands.append(cmd)
        self._current["voice.commands.custom"] = commands

        # 更新列表
        self._refresh_commands_list()
        # 指令操作立即持久化：用户添加后即使直接关闭面板也不丢失
        self._save_commands_now()

    def _edit_command(self):
        """编辑选中的指令。"""
        row = self._commands_list.currentRow()
        if row < 0:
            return

        commands = self._current.get("voice.commands.custom", [])
        if row >= len(commands):
            return

        cmd = commands[row]

        dlg = _CommandDialog(
            self,
            title="编辑指令",
            trigger=cmd.get("trigger", ""),
            action=cmd.get("action", ""),
            custom_text=cmd.get("custom_text", ""),
            custom_url=cmd.get("custom_url", ""),
            match_type=cmd.get("match_type", "contains"),
            require_wake_word=cmd.get("require_wake_word"),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        cmd["trigger"] = dlg.trigger_text()
        cmd["action"] = dlg.action_key()
        cmd["match_type"] = dlg.match_type()
        cmd["require_wake_word"] = dlg.require_wake_word()

        # 清理旧的自定义字段并写入新值
        cmd.pop("custom_text", None)
        cmd.pop("custom_url", None)
        if dlg.custom_text():
            cmd["custom_text"] = dlg.custom_text()
        if dlg.custom_url():
            cmd["custom_url"] = dlg.custom_url()

        self._current["voice.commands.custom"] = commands

        # 更新列表
        self._refresh_commands_list()
        self._save_commands_now()

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
        self._save_commands_now()

    def _refresh_commands_list(self):
        """刷新指令列表显示。"""
        self._commands_list.clear()
        commands = self._current.get("voice.commands.custom", [])
        for cmd in commands:
            trigger = cmd.get("trigger", "")
            action = cmd.get("action", "")
            if action == "open_website":
                url = cmd.get("custom_url", "")
                label = f"{trigger} -> 打开 {url}"
            elif action == "show_dialogue":
                text = cmd.get("custom_text", "")
                label = f"{trigger} -> 说 '{text}'"
            else:
                label = f"{trigger} -> {action}"

            # 标出触发条件，避免用户以为随口一句话就能执行外部动作
            marks = []
            if cmd.get("require_wake_word"):
                marks.append("需唤醒")
            elif cmd.get("action", "") in ("open_website",):
                marks.append("需唤醒(默认)")
            if cmd.get("match_type") == "exact":
                marks.append("精确")
            if marks:
                label = f"[{'/'.join(marks)}] {label}"

            self._commands_list.addItem(label)

    def _apply_preview(self, key, value):
        """更新临时配置，发出预览信号，"""
        if self._updating:
            return
        self._current[key] = value
        self._dirty = True
        self.preview_changed.emit(self._current.copy())

    @staticmethod
    def _flatten_dict(prefix: str, data: dict) -> dict:
        """将嵌套 dict 展开为点分路径的扁平 dict。

        例如 {"window": {"opacity": 0.95}} -> {"window.opacity": 0.95}
        """
        result = {}
        for key, value in data.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(SettingsPanel._flatten_dict(new_key, value))
            else:
                result[new_key] = value
        return result

    def _load_settings(self):
        """从配置文件加载，初始化临时和初始状态"""
        # get_all() 返回嵌套 dict，这里展开为点分路径扁平 dict，
        # 与 window.size_scale / voice.commands.custom 等点分键保持一致
        self._current = self._flatten_dict("", self._config.get_all())
        self._initial = self._current.copy()

        self._updating = True
        try:
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
            self._voice_enabled_check.setChecked(
                self._current.get("voice.enabled", False)
            )

            # 加载唤醒词
            wake_words = self._current.get(
                "voice.commands.wake_words", ["hey nina", "小猫", "nina"]
            )
            self._wake_words_input.setText(", ".join(wake_words))

            # 加载麦克风选择
            self._refresh_mic_devices(
                self._current.get("voice.input_device") or ""
            )

            # 加载云端 Key（assemblyai.api_key 优先，回落到顶层 voice.api_key）
            self._api_key_input.setText(
                self._current.get("voice.assemblyai.api_key")
                or self._current.get("voice.api_key")
                or ""
            )

            # 加载指令列表
            self._refresh_commands_list()

            # 更新标签显示
            self._size_label.setText(f"{self._size_slider.value()}%")
            self._opacity_label.setText(f"{self._opacity_slider.value()}%")
        finally:
            self._updating = False

    def _save_settings(self):
        """保存当前临时设置到配置文件。"""
        # 必须在覆盖 _initial 之前取旧值，用于判断语音是否刚被开启
        voice_was_enabled = bool(self._initial.get("voice.enabled"))

        _PANEL_KEYS = (
            "window.size_scale",
            "window.opacity",
            "window.always_on_top",
            "behavior.auto_move",
            "behavior.dialogue_enabled",
            "voice.enabled",
        )
        for key in _PANEL_KEYS:
            if key in self._current:
                self._config.set(key, self._current[key])

        # 保存云端 Key。字段为空表示用户主动清空，照实写入即可；
        # 若 Key 来自环境变量 ASSEMBLYAI_API_KEY，这里写空也不影响使用。
        self._config.set(
            "voice.assemblyai.api_key",
            self._api_key_input.text().strip(),
        )

        # 保存唤醒词
        wake_text = self._wake_words_input.text()
        wake_words = [w.strip() for w in wake_text.split(",") if w.strip()]
        self._config.set("voice.commands.wake_words", wake_words)

        # 保存麦克风选择（存设备名，端口/索引漂移不影响匹配）
        mic_name = self._mic_combo.currentData()
        mic_was = self._initial.get("voice.input_device") or ""
        self._config.set("voice.input_device", mic_name or None)

        # 保存自定义指令
        commands = self._current.get("voice.commands.custom", [])
        self._config.set("voice.commands.custom", commands)

        if not self._config.save():
            # 落盘失败时保持 _dirty=True，让用户关闭面板时仍能回滚/重试，
            # 否则内存标记为「已保存」但磁盘仍是旧值，状态不一致
            self._dirty = True
            logger.error("保存设置失败，保留未保存状态以便重试")
            # 必须让用户看见：否则表现为「点了保存没反应」
            QMessageBox.critical(
                self,
                "保存失败",
                "无法写入配置文件。\n\n"
                "设置保存在用户目录下：\n"
                "%APPDATA%\\GBC Nina\\config\\user.json\n\n"
                "请检查该目录是否有写入权限；也可以在系统环境变量\n"
                "GBC_NINA_HOME 中指定一个可写的目录作为数据位置。\n\n"
                "详细信息见 logs 目录下的日志文件。",
            )
            return

        self._initial = self._current.copy()
        self._dirty = False

        # 语音开关/麦克风变化都需要重启才生效（麦克风与 Provider 在
        # start() 时创建），这里明确告知，避免用户以为保存后立刻生效
        if self._current.get("voice.enabled") and not voice_was_enabled:
            QMessageBox.information(
                self,
                "语音已开启",
                "语音开关已保存，但需要重启 Nina 才会生效。\n\n"
                "麦克风与语音引擎在程序启动时初始化，"
                "如需立即启用请退出后重新运行。",
            )
        elif (mic_name or "") != mic_was:
            QMessageBox.information(
                self,
                "麦克风已更改",
                "麦克风设置已保存，但需要重启 Nina 才会生效。\n\n"
                "语音采集在程序启动时初始化，"
                "如需立即切换请退出后重新运行。",
            )

        self.settings_changed.emit()
        self._event_bus.emit("settings.changed", self._current.copy())

    def _save_commands_now(self):
        """立即保存指令和唤醒词。

        指令的添加/编辑/删除是用户明确的一次性操作，
        立即持久化可以避免用户添加后直接关闭面板时
        closeEvent 因 _dirty =True 静默丢弃改动。
        """
        wake_text = self._wake_words_input.text()
        wake_words = [w.strip() for w in wake_text.split(",") if w.strip()]
        self._config.set("voice.commands.wake_words", wake_words)
        self._config.set(
            "voice.commands.custom",
            self._current.get("voice.commands.custom", []),
        )
        if not self._config.save():
            # 必须显式置脏：指令的添加/编辑/删除走立即保存路径，
            # 进入时 _dirty 可能仍是 False。若不置脏，关闭面板时
            # closeEvent 会认为「无未保存改动」而放行，
            # 结果 ConfigManager 内存里是新指令、磁盘上却是旧的。
            self._dirty = True
            logger.error("保存指令失败，保留未保存状态以便重试")
            return
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
        self._mic_combo.setCurrentIndex(0)

        self._size_label.setText(f"{self._size_slider.value()}%")
        self._opacity_label.setText(f"{self._opacity_slider.value()}%")

        # 应用预览（不保存）
        self.preview_changed.emit(self._current.copy())
        self._dirty = True

    def closeEvent(self, event):
        """关闭窗口时，如果未保存则恢复初始设置"""
        self._stop_mic_monitor()
        if self._dirty:
            # 恢复到打开时的状态
            self._current = self._initial.copy()
            self._updating = True
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
            self._wake_words_input.setText(
                ", ".join(
                    self._current.get(
                        "voice.commands.wake_words",
                        ["hey nina", "小猫", "nina"],
                    )
                )
            )
            self._refresh_commands_list()
            self._size_label.setText(f"{self._size_slider.value()}%")
            self._opacity_label.setText(f"{self._opacity_slider.value()}%")
            self._updating = False
            # 通知主窗口恢复
            self.preview_changed.emit(self._current.copy())
            self._dirty = False

        event.accept()


class _CommandDialog(QDialog):
    """指令编辑表单：触发词 + 动作下拉 + 条件字段（网址/文本）同屏显示。"""

    ACTIONS = [
        ("show_time", "显示时间"),
        ("show_date", "显示日期"),
        ("show_greeting", "显示问候语"),
        ("play_happy", "播放开心动画"),
        ("play_dance", "播放跳舞动画"),
        ("show_status", "显示状态"),
        ("show_dialogue", "显示自定义对话"),
        ("open_website", "打开网站(需输入网址)"),
    ]

    def __init__(
        self, parent=None, title="指令",
        trigger="", action="", custom_text="", custom_url="",
        match_type="contains", require_wake_word=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        # 用户是否手动改过唤醒词开关；改过后不再按动作自动调整默认值
        self._wake_manual = False

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("触发词（语音说出的内容）:"))
        self._trigger_edit = QLineEdit(trigger)
        self._trigger_edit.setPlaceholderText("例如：打开百度")
        layout.addWidget(self._trigger_edit)

        layout.addWidget(QLabel("匹配方式:"))
        self._match_combo = QComboBox()
        self._match_combo.addItem("包含匹配（说出整句即可触发）", "contains")
        self._match_combo.addItem("精确匹配（必须只说触发词）", "exact")
        layout.addWidget(self._match_combo)

        layout.addWidget(QLabel("动作:"))
        self._action_combo = QComboBox()
        for key, label in self.ACTIONS:
            self._action_combo.addItem(label, key)
        layout.addWidget(self._action_combo)

        self._extra_label = QLabel("")
        layout.addWidget(self._extra_label)

        self._extra_edit = QLineEdit()
        self._extra_edit.setPlaceholderText("")
        layout.addWidget(self._extra_edit)

        # 有外部副作用的动作默认要求先唤醒，避免日常语音误触发
        self._wake_check = QCheckBox("需要先说唤醒词")
        self._wake_check.setToolTip(
            "开启后必须先说唤醒词（或在唤醒后的 5 秒内说）才会执行。\n"
            "「打开网站」这类会切走窗口的动作建议保持开启。"
        )
        # 用 clicked 而非 stateChanged：setChecked() 是程序化设置，
        # 也会发 stateChanged，若监听它会导致「刚自动勾上的默认值」
        # 被误记为用户手动改过，之后再也不随动作更新默认值。
        self._wake_check.clicked.connect(self._on_wake_toggled)
        layout.addWidget(self._wake_check)

        self._action_combo.currentIndexChanged.connect(self._on_action_changed)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 初始选中匹配方式（缺省 contains，兼容既有配置）
        idx = self._match_combo.findData(match_type or "contains")
        if idx >= 0:
            self._match_combo.setCurrentIndex(idx)

        # 初始选中动作（若有）
        if action:
            idx = self._action_combo.findData(action)
            if idx >= 0:
                self._action_combo.setCurrentIndex(idx)
        self._on_action_changed()

        # 编辑既有指令时回填原有网址/文本（之前这两个参数被忽略，
        # 导致编辑时输入框是空的，不重填就会把用户的网址清掉）
        if self.action_key() == "open_website":
            self._extra_edit.setText(custom_url)
        elif self.action_key() == "show_dialogue":
            self._extra_edit.setText(custom_text)

        # 回填唤醒词开关：显式值优先，否则按动作风险取默认
        if require_wake_word is None:
            self._wake_check.setChecked(
                self.action_key() in ("open_website",)
            )
        else:
            self._wake_check.setChecked(bool(require_wake_word))
            self._wake_manual = True

        self._trigger_edit.setFocus()

    def _on_wake_toggled(self):
        """用户手动切换后不再按动作自动改默认值"""
        self._wake_manual = True

    def _on_action_changed(self):
        """根据所选动作显示/隐藏附加输入框，并刷新唤醒词默认值。"""
        key = self._action_combo.currentData()
        if key == "open_website":
            self._extra_label.setText("网址:")
            self._extra_edit.setPlaceholderText("https://example.com")
            self._extra_edit.setVisible(True)
            self._extra_label.setVisible(True)
        elif key == "show_dialogue":
            self._extra_label.setText("显示的文本:")
            self._extra_edit.setPlaceholderText("例如：今天也要加油！")
            self._extra_edit.setVisible(True)
            self._extra_label.setVisible(True)
        else:
            self._extra_label.setVisible(False)
            self._extra_edit.setVisible(False)
        self._extra_edit.clear()
        if not self._wake_manual:
            self._wake_check.setChecked(key in ("open_website",))

    def _on_ok(self):
        """校验输入：触发词必填，网址/文本按需必填。"""
        if not self._trigger_edit.text().strip():
            self._trigger_edit.setFocus()
            return
        key = self._action_combo.currentData()
        if key == "open_website" and not self._extra_edit.text().strip():
            self._extra_edit.setFocus()
            return
        self.accept()

    def trigger_text(self):
        return self._trigger_edit.text().strip()

    def action_key(self):
        return self._action_combo.currentData()

    def match_type(self):
        return self._match_combo.currentData()

    def require_wake_word(self):
        return self._wake_check.isChecked()

    def custom_text(self):
        key = self._action_combo.currentData()
        if key == "show_dialogue":
            return self._extra_edit.text().strip()
        return ""

    def custom_url(self):
        key = self._action_combo.currentData()
        if key == "open_website":
            return self._extra_edit.text().strip()
        return ""
