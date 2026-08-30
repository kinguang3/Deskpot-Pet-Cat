"""GBC Nina 桌面猫咪 - 程序入口"""

import sys
import os
import platform

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from src.utils.logger import setup_logger, get_logger


def main():
    """程序入口。"""
    # 初始化日志系统
    debug_mode = os.environ.get("NINA_DEBUG", "0") == "1"
    setup_logger(debug_mode=debug_mode)
    logger = get_logger("main")

    # 高 DPI 支持
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    logger.info("GBC Nina starting")
    logger.info("Python: %s", platform.python_version())
    logger.info("Platform: %s %s", platform.system(), platform.release())
    logger.info("Debug mode: %s", debug_mode)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，靠托盘退出
    app.setApplicationName("GBC Nina")
    app.setApplicationVersion("0.1.0")

    # 记录 PySide6 版本
    try:
        import PySide6
        logger.info("PySide6: %s", PySide6.__version__)
    except AttributeError:
        logger.debug("PySide6 version not available")

    # 创建并启动应用管理器
    from src.app import App
    nina = App()
    nina.start()

    logger.info("Entering event loop")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
