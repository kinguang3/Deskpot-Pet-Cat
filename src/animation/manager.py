# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""动画管理器模块

控制动画播放、切换、循环、帧率。
通过 EventBus 广播动画状态变化。
"""

from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtGui import QPixmap

from src.animation.sprites import SpriteLoader
from src.core.event_bus import EventBus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnimationManager(QObject):
    """管理精灵图动画的播放和切换。"""

    frame_changed = Signal(QPixmap)  # 每帧切换时发出信号

    def __init__(self, sprite_loader: SpriteLoader, parent=None):
        super().__init__(parent)
        self._loader = sprite_loader
        self._event_bus = EventBus()

        self._current_animation: str = ""
        self._frames: list[QPixmap] = []
        self._current_frame: int = 0
        self._fps: int = 6
        self._loop: bool = True
        self._playing: bool = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        # 默认帧率配置
        self._fps_map = {
            "idle": 6,
            "walk_left": 8,
            "walk_right": 8,
            "typing": 8,
            "typing_red": 8,
            "watching": 6,
            "sleep": 2,
        }
        logger.debug("AnimationManager initialized")

    @property
    def current_animation(self) -> str:
        return self._current_animation

    @property
    def current_frame(self) -> QPixmap:
        if self._frames and 0 <= self._current_frame < len(self._frames):
            return self._frames[self._current_frame]
        return QPixmap()

    @property
    def frame_size(self) -> tuple[int, int]:
        if self._frames:
            return (self._frames[0].width(), self._frames[0].height())
        return (0, 0)

    def play(self, animation_name: str, loop: bool = True):
        """播放指定动画。

        如果已经在播放同一动画，不做任何操作。

        Args:
            animation_name: 动画名称
            loop: 是否循环播放
        """
        if animation_name == self._current_animation and self._playing:
            return

        frames = self._loader.load_animation(animation_name)
        if not frames:
            logger.warning("No frames for animation: %s", animation_name)
            return

        old_anim = self._current_animation
        self.stop()

        self._current_animation = animation_name
        self._frames = frames
        self._current_frame = 0
        self._loop = loop
        self._fps = self._fps_map.get(animation_name, 6)

        self._playing = True
        self._timer.start(1000 // self._fps)

        # 发送第一帧
        self.frame_changed.emit(self.current_frame)

        # 广播动画开始事件
        self._event_bus.emit(
            "animation.started",
            {
                "animation": animation_name,
                "frame_count": len(frames),
                "loop": loop,
            },
        )

    def stop(self):
        """停止当前动画。"""
        self._timer.stop()
        was_playing = self._playing
        self._playing = False

        if was_playing and self._current_animation:
            self._event_bus.emit(
                "animation.stopped",
                {
                    "animation": self._current_animation,
                },
            )

    def pause(self):
        """暂停动画。"""
        if self._playing:
            self._timer.stop()
            logger.debug("Animation paused: %s", self._current_animation)

    def resume(self):
        """恢复动画。"""
        if self._playing and self._frames:
            self._timer.start(1000 // self._fps)
            logger.debug("Animation resumed: %s", self._current_animation)

    def set_fps(self, fps: int):
        """动态修改帧率。"""
        self._fps = max(1, fps)
        if self._playing:
            self._timer.setInterval(1000 // self._fps)

    def _on_tick(self):
        """定时器回调，切换到下一帧。"""
        if not self._frames:
            return

        self._current_frame += 1

        if self._current_frame >= len(self._frames):
            if self._loop:
                self._current_frame = 0
                self._event_bus.emit(
                    "animation.looped",
                    {
                        "animation": self._current_animation,
                    },
                )
            else:
                self._current_frame = len(self._frames) - 1
                anim_name = self._current_animation
                self.stop()
                self._event_bus.emit(
                    "animation.finished",
                    {
                        "animation": anim_name,
                    },
                )
                logger.debug("Animation finished: %s", anim_name)
                return

        self.frame_changed.emit(self.current_frame)
