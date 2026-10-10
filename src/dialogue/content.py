# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""对话内容管理模块

管理 Nina 的对话内容。
按时间、用户行为与语音情绪动态选择对话。
"""

import random
from datetime import datetime


class DialogueContent:
    """对话内容管理器。"""

    def __init__(self):
        # ─── 基础对话 ───

        self._idle_lines = [
            "有点无聊呢...",
            "要不要摸摸我？",
            "你在忙什么呀？",
            "嘿嘿~",
            "我要发呆一会儿。",
        ]

        self._click_lines = [
            "嗯？",
            "干嘛啦~",
            "别戳我！",
            "好痒！",
            "喵！",
            "你在逗我吗？",
        ]

        self._wake_lines = [
            "我醒了！",
            "嗯...几点了？",
            "伸个懒腰~",
            "你回来啦~",
        ]

        self._hover_lines = [
            "你在看我吗？",
            "嘿嘿~",
            "怎么了？",
        ]

        # ─── 时段对话 ───

        self._morning_lines = [
            "早上好！新的一天开始了~",
            "早安！今天也要加油哦！",
            "起床啦！",
            "阳光真舒服~",
        ]

        self._afternoon_lines = [
            "下午好~",
            "下午茶时间！",
            "有点困了呢...",
            "你在忙工作吗？",
        ]

        self._evening_lines = [
            "晚上好~",
            "今天辛苦了。",
            "要不要休息一下？",
            "天黑了呢。",
        ]

        self._night_lines = [
            "这么晚了还不睡吗？",
            "夜深了哦...",
            "注意身体呀。",
            "早点休息吧~",
        ]

        self._late_night_lines = [
            "都这个时间了...",
            "熬夜对身体不好哦。",
            "我好困...",
            "你要通宵吗？",
        ]

        # ─── 语音情绪反应 ───

        self._voice_happy_lines = [
            "你听起来很开心呢~",
            "听到你开心我也开心！",
            "嘿嘿~",
            "心情真好！",
        ]

        self._voice_sad_lines = [
            "你怎么了？",
            "别难过哦~",
            "我陪着你呢。",
            "抱抱~",
        ]

        self._voice_angry_lines = [
            "你生气了吗？",
            "别生气啦~",
            "深呼吸~",
            "冷静一下哦。",
        ]

        self._voice_neutral_lines = [
            "嗯？",
            "我在听哦。",
            "怎么了？",
            "说吧说吧~",
        ]

    # ─── 基础获取方法 ───

    def get_idle_line(self) -> str:
        return random.choice(self._idle_lines)

    def get_click_line(self) -> str:
        return random.choice(self._click_lines)

    def get_wake_line(self) -> str:
        return random.choice(self._wake_lines)

    def get_hover_line(self) -> str:
        return random.choice(self._hover_lines)

    def get_time_based_line(self) -> str:
        """根据当前时间返回合适的对话。"""
        hour = datetime.now().hour

        if 5 <= hour < 9:
            return random.choice(self._morning_lines)
        elif 9 <= hour < 17:
            return random.choice(self._afternoon_lines)
        elif 17 <= hour < 21:
            return random.choice(self._evening_lines)
        elif hour >= 21 or hour < 1:
            return random.choice(self._night_lines)
        else:
            return random.choice(self._late_night_lines)

    def get_voice_emotion_line(self, emotion: str) -> str:
        """根据语音情绪返回反应台词。"""
        emotion = emotion.upper()
        if emotion == "HAPPY":
            return random.choice(self._voice_happy_lines)
        elif emotion == "SAD":
            return random.choice(self._voice_sad_lines)
        elif emotion == "ANGRY":
            return random.choice(self._voice_angry_lines)
        else:
            return random.choice(self._voice_neutral_lines)
