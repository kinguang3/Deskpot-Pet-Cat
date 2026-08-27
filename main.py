"""GBC Nina 桌面猫咪 - 程序入口"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.app import App


def main():
    """程序入口。"""
    # 高 DPI 支持
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，靠托盘退出
    app.setApplicationName("GBC Nina")
    app.setApplicationVersion("0.1.0")

    # 创建并启动应用管理器
    nina = App()
    nina.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
