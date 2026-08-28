"""对话气泡模块

在宠物头顶显示对话气泡。
"""

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QFont, QPainterPath


class DialogueBubble(QWidget):
    """对话气泡 UI 组件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        )
        self.setVisible(False)

        self._text: str = ""
        self._display_timer = QTimer(self)
        self._display_timer.setSingleShot(True)
        self._display_timer.timeout.connect(self.hide_bubble)

        self._opacity_effect = None
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._on_fade)

    def _on_fade(self):
        """淡出动画完成后隐藏。"""
        self.hide_bubble()

    def show_text(self, text: str, duration: int = 3000):
        """显示对话文本。

        Args:
            text: 要显示的文本
            duration: 显示时长（毫秒）
        """
        if not text:
            return

        self._text = text
        self._adjust_size()
        self.setVisible(True)
        self.update()

        self._display_timer.start(duration)

    def hide_bubble(self):
        """隐藏气泡。"""
        self.setVisible(False)
        self._text = ""

    def _adjust_size(self):
        """根据文本内容调整气泡大小。"""
        font = QFont("Microsoft YaHei", 10)
        fm = self.fontMetrics()
        text_rect = fm.boundingRect(
            0, 0, 300, 1000, Qt.TextFlag.TextWordWrap, self._text
        )

        padding = 20
        width = min(text_rect.width() + padding * 2, 300)
        height = text_rect.height() + padding * 2

        self.setFixedSize(int(width), int(height))

    def paintEvent(self, event):
        """绘制气泡背景和文本。"""
        if not self._text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制圆角矩形气泡背景
        path = QPainterPath()
        rect = self.rect().adjusted(2, 2, -2, -2)
        path.addRoundedRect(
            rect.x(), rect.y(), rect.width(), rect.height(), 12, 12
        )

        # 气泡背景色
        painter.fillPath(path, QColor(255, 255, 255, 230))

        # 气泡边框
        painter.setPen(QColor(200, 200, 200, 180))
        painter.drawPath(path)

        # 绘制三角形小尾巴（底部中间）
        tail_path = QPainterPath()
        center_x = rect.center().x()
        tail_path.moveTo(center_x - 8, rect.bottom() - 1)
        tail_path.lineTo(center_x, rect.bottom() + 10)
        tail_path.lineTo(center_x + 8, rect.bottom() - 1)
        tail_path.closeSubpath()
        painter.fillPath(tail_path, QColor(255, 255, 255, 230))
        painter.drawPath(tail_path)

        # 绘制文本
        painter.setPen(QColor(60, 60, 60))
        painter.setFont(QFont("Microsoft YaHei", 10))
        text_rect = rect.adjusted(10, 10, -10, -10)
        painter.drawText(
            text_rect,
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter,
            self._text,
        )

        painter.end()
