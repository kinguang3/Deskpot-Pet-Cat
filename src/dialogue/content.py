# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""对话内容管理模块

管理 Nina 的对话内容。
根据时间、状态、用户行为动态选择对话。
"""

import random
from datetime import datetime


class DialogueContent:
    """对话内容管理器。"""

    def __init__(self):
        self._greetings = [
            "喵~",
            "你来啦！",
            "今天也辛苦了~",
            "我在等你呢。",
        ]

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

        self._drag_lines = [
            "放我下来！",
            "头好晕...",
            "我要吐了！",
            "快放下我！",
        ]

        self._sleep_lines = [
            "zzZ...",
            "好困...",
            "让我睡一会儿...",
            "呼噜噜...",
        ]

        self._wake_lines = [
            "我醒了！",
            "嗯...几点了？",
            "伸个懒腰~",
        ]

        self._morning_lines = [
            "早上好！新的一天开始了~",
            "早安！今天也要加油哦！",
            "起床啦！",
        ]

        self._afternoon_lines = [
            "下午好~",
            "下午茶时间！",
            "有点困了呢...",
        ]

        self._evening_lines = [
            "晚上好~",
            "今天辛苦了。",
            "要不要休息一下？",
        ]

        self._night_lines = [
            "这么晚了还不睡吗？",
            "夜深了哦...",
            "注意身体呀。",
            "早点休息吧~",
        ]

        self._hover_lines = [
            "你在看我吗？",
            "嘿嘿~",
            "怎么了？",
        ]

        self._long_inactive_lines = [
            "你还在吗？",
            "好久没理我了...",
            "我想你了。",
            "你是不是忘了我？",
        ]

    def get_greeting(self) -> str:
        return random.choice(self._greetings)

    def get_idle_line(self) -> str:
        return random.choice(self._idle_lines)

    def get_click_line(self) -> str:
        return random.choice(self._click_lines)

    def get_drag_line(self) -> str:
        return random.choice(self._drag_lines)

    def get_sleep_line(self) -> str:
        return random.choice(self._sleep_lines)

    def get_wake_line(self) -> str:
        return random.choice(self._wake_lines)

    def get_hover_line(self) -> str:
        return random.choice(self._hover_lines)

    def get_long_inactive_line(self) -> str:
        return random.choice(self._long_inactive_lines)

    def get_time_based_line(self) -> str:
        """根据当前时间返回合适的对话。"""
        hour = datetime.now().hour

        if 5 <= hour < 9:
            return random.choice(self._morning_lines)
        elif 9 <= hour < 17:
            return random.choice(self._afternoon_lines)
        elif 17 <= hour < 21:
            return random.choice(self._evening_lines)
        else:
            return random.choice(self._night_lines)
