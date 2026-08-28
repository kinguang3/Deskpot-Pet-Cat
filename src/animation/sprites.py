"""精灵图加载模块

从 assets 目录加载猫咪精灵图，按动画类型分组缓存。
"""

from pathlib import Path
from PySide6.QtGui import QPixmap

# 动画名称 -> 文件名前缀的映射
ANIMATION_MAP = {
    "idle": "cat_idle",
    "walk_left": "cat_walk_left",
    "walk_right": "cat_walk_right",
    "typing": "cat_typing",
    "typing_red": "cat_typing_red",
    "watching": "cat_watching",
    "sleep": "cat_sleep",
}

# 单帧图片（非动画）
SINGLE_FRAME_MAP = {
    "tall": "cat_tall",
    "long": "cat_long",
    "melt": "cat_melt",
    "glitch": "cat_glitch",
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
        self._single_cache: dict[str, QPixmap] = {}
        self._frame_size: dict[str, tuple[int, int]] = {}

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
            print(f"[SpriteLoader] Unknown animation: {name}")
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
            w, h = frames[0].width(), frames[0].height()
            self._frame_size[name] = (w, h)
            print(
                f"[SpriteLoader] Loaded animation '{name}': {len(frames)} frames, {w}x{h}"
            )

        return frames

    def load_single(self, name: str) -> QPixmap:
        """加载单帧图片。

        Args:
            name: 图片名称，如 "tall", "melt"
        """
        if name in self._single_cache:
            return self._single_cache[name]

        prefix = SINGLE_FRAME_MAP.get(name)
        if prefix is None:
            print(f"[SpriteLoader] Unknown single frame: {name}")
            return QPixmap()

        file_path = self._assets_dir / f"{prefix}.png"
        if not file_path.exists():
            print(f"[SpriteLoader] File not found: {file_path}")
            return QPixmap()

        pixmap = QPixmap(str(file_path))
        if not pixmap.isNull():
            self._single_cache[name] = pixmap

        return pixmap

    def get_frame_size(self, name: str) -> tuple[int, int]:
        """获取动画的帧尺寸。"""
        if name in self._frame_size:
            return self._frame_size[name]

        self.load_animation(name)
        return self._frame_size.get(name, (0, 0))

    def load_all(self):
        """预加载所有动画。"""
        for name in ANIMATION_MAP:
            self.load_animation(name)
        for name in SINGLE_FRAME_MAP:
            self.load_single(name)
