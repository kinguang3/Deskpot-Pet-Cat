# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""精灵图加载模块

从 assets 目录加载猫咪精灵图，按动画类型分组缓存。
"""

from pathlib import Path
from PySide6.QtGui import QPixmap

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 动画名称 -> 文件名前缀的映射
ANIMATION_MAP = {
    "idle": "cat_idle",
    "walk_left": "cat_walk_left",
    "walk_right": "cat_walk_right",
    "typing": "cat_typing",
    "watching": "cat_watching",
    "sleep": "cat_sleep",
}


class SpriteLoader:
    """精灵图加载器，负责从磁盘加载并缓存精灵图。"""

    def __init__(self, assets_dir: str = None):
        if assets_dir is None:
            assets_dir = str(
                Path(__file__).resolve().parent.parent.parent / "assets"
            )
        self._assets_dir = Path(assets_dir)
        self._cache: dict[str, list[QPixmap]] = {}
        logger.debug("SpriteLoader initialized (dir: %s)", self._assets_dir)

    def load_animation(self, name: str) -> list[QPixmap]:
        """加载一个动画的所有帧。

        Args:
            name: 动画名称，如 "idle", "walk_left"

        Returns:
            QPixmap 列表，按帧顺序排列
        """
        if name in self._cache:
            return self._cache[name]

        prefix = ANIMATION_MAP.get(name)
        if prefix is None:
            logger.warning("Unknown animation: %s", name)
            return []

        frames = []
        for i in range(1, 100):  # 最多尝试 100 帧
            file_path = self._assets_dir / f"{prefix}{i}.png"
            if not file_path.exists():
                break
            pixmap = QPixmap(str(file_path))
            if not pixmap.isNull():
                frames.append(pixmap)

        if frames:
            self._cache[name] = frames

        return frames
