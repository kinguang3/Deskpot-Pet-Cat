# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""隐私协议与首次运行向导

背景：本项目会打开麦克风录音，并且在 hybrid 模式下会把音频片段上传到
AssemblyAI 云端做转写。此前全项目没有任何告知或同意入口
（`用户协议` / `隐私` / `agree` / `consent` 等关键词零命中），属于合规缺口。

本模块提供两个界面：
- PrivacyDialog：首次运行强制展示的隐私协议，必须勾选同意才能继续
- VoiceOptInDialog：同意协议后，单独就「是否开启语音」再征询一次

设计上把「同意协议」和「开启语音」拆成两步，避免把麦克风授权混在
协议里让用户以为勾选协议就等于授权录音。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from src.utils.logger import get_logger

logger = get_logger(__name__)

AGREEMENT_HTML = r"""
<h3 style="margin-bottom:6px;">Nina 隐私协议</h3>

<p><b>本软件是本地运行的桌面宠物，除下述两项外不收集、不上传任何数据。</b></p>

<h4>1. 麦克风</h4>
<p>仅在你<b>主动开启</b>语音功能后，Nina 才会请求麦克风权限并录音。
默认状态下麦克风完全关闭，不采集任何声音。</p>

<h4>2. 云端转写（重要）</h4>
<p>当前默认使用 <code>hybrid</code> 模式：本地的 SenseVoice 引擎在
<b>本机离线运行</b>，但当本地引擎不可用时会<b>自动回退</b>到
AssemblyAI 云服务。此时<b>你的语音片段会被上传到 AssemblyAI</b>
（assemblyai.com）进行转写。</p>
<p>上传由第三方服务商处理，受其隐私政策约束：<br>
<a href="https://assemblyai.com/privacy">assemblyai.com/privacy</a></p>
<p>若你不同意音频外发，请保持语音功能关闭，或把
<code>voice.provider</code> 改为仅本地方案。</p>

<h4>3. 本地存储的数据</h4>
<p>以下内容<b>仅保存在你自己的电脑上</b>，不会上传：</p>
<ul>
  <li>互动记忆（互动次数、心情变化），位于用户目录 <code>data/</code></li>
  <li>窗口大小、透明度、行为参数等设置，位于 <code>config/</code></li>
  <li>运行日志，位于 <code>logs/</code></li>
  <li>临时音频中间文件，位于 <code>temp/</code>（推理后即删除）</li>
</ul>
<p>新版将用户数据保存到系统用户目录（Windows 下为
<code>%APPDATA%\GBC Nina\</code>），卸载程序不会删除这些数据。
需要彻底清除时，请手动删除上述用户目录。</p>

<h4>4. API Key</h4>
<p>如果你启用云端转写，需要自行提供 AssemblyAI API Key。
Key 以<b>明文</b>保存在本机 <code>config/user.json</code>，
不会上传到除 AssemblyAI 外的任何服务。请勿把包含 Key 的配置文件
提交到公开仓库或分享给他人。</p>

<h4>5. 开源许可</h4>
<p>本项目采用 MIT License 开源。第三方组件（PySide6、numpy 等）的
许可声明见项目 README。</p>

<p style="color:#888; font-size:11px; margin-top:12px;">
本协议为 v0.1.1 的实现说明，用于明确告知数据处理行为。
正式发布前建议由法务审核并补充主体信息（运营者、联系方式、
生效日期、争议解决条款等）。
</p>
"""


class PrivacyDialog(QDialog):
    """首次运行的隐私协议弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nina - 隐私协议")
        self.setModal(True)
        self.setMinimumSize(560, 520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "首次运行需要确认以下数据处理方式。"
            "<br>你可以只使用桌宠功能而不开启语音。"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._browser = QTextBrowser()
        self._browser.setHtml(AGREEMENT_HTML)
        self._browser.setOpenExternalLinks(True)
        layout.addWidget(self._browser, 1)

        self._agree_check = QCheckBox("我已阅读并同意以上协议")
        layout.addWidget(self._agree_check)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._exit_btn = QPushButton("不同意并退出")
        self._exit_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._exit_btn)

        self._accept_btn = QPushButton("同意并继续")
        # 未勾选时禁用，避免空点
        self._agree_check.toggled.connect(
            self._accept_btn.setEnabled
        )
        self._accept_btn.setEnabled(False)
        self._accept_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._accept_btn)

        layout.addLayout(btn_layout)

    @property
    def is_accepted(self) -> bool:
        """用户是否同意（只认勾选，reject 不算同意）。

        注意：不能命名为 `accepted`——QDialog 已有同名的 accepted 信号，
        Python 属性会被 Qt 信号遮蔽，访问到的是 SignalInstance 而非 bool。
        """
        return self.result() == QDialog.DialogCode.Accepted and (
            self._agree_check.isChecked()
        )


class VoiceOptInDialog(QDialog):
    """同意协议后，就「是否开启语音」单独征询。

    默认否，用户主动勾选才会开启麦克风。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nina - 语音功能")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("<b>是否开启语音功能？</b>")
        layout.addWidget(title)

        desc = QLabel(
            "开启后 Nina 会使用麦克风听你说话，并用语音指令做出反应。\n\n"
            "<b>开启会：</b>\n"
            "· 请求并占用麦克风\n"
            "· 本地识别失败时，语音片段可能上传至 AssemblyAI 云端\n\n"
            "<b>不开启：</b>\n"
            "· 麦克风完全关闭，不采集任何声音\n"
            "· 其余桌宠功能（动画、对话、互动、记忆）不受影响\n\n"
            "之后可以随时在「设置」里开关。"
        )
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(desc)

        layout.addStretch()

        btn_layout = QHBoxLayout()

        self._off_btn = QPushButton("暂不开启")
        self._off_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._off_btn)

        self._on_btn = QPushButton("开启语音")
        self._on_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._on_btn)

        layout.addLayout(btn_layout)

    @property
    def wants_voice(self) -> bool:
        return self.result() == QDialog.DialogCode.Accepted
