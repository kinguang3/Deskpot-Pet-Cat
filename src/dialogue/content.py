# Copyright (c) 2026 kinguang3<548635581@qq.com>, CrimsonSeraph<ltyy.leoyu@gmail.com>
# SPDX-License-Identifier: MIT

"""对话内容管理模块

管理 Nina 的对话内容。
根据时间、状态、用户行为、内部情感动态选择对话。
"""

import random
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DialogueContent:
    """对话内容管理器。"""

    def __init__(self):
        # ─── 基础对话 ───
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
            "你回来啦~",
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

        # ─── 上下文对话 ───

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

        # ─── 情感对话 ───

        self._happy_lines = [
            "好开心！",
            "嘿嘿~",
            "心情真好！",
            "最喜欢你了！",
        ]

        self._sleepy_lines = [
            "好困...",
            "眼皮好重...",
            "想睡觉了...",
            "打个哈欠~",
            "有点撑不住了...",
        ]

        self._energetic_lines = [
            "精力充沛！",
            "想跑一跑！",
            "今天状态很好！",
            "动起来！",
        ]

        self._bored_lines = [
            "好无聊...",
            "没什么事做呢...",
            "要不要玩点什么？",
            "发呆中...",
        ]

        # ─── 重复点击反应 ───

        self._repeat_click_lines = [
            "嗯？",
            "又来？",
            "你很闲吗？",
            "别一直戳啦！",
            "我要生气了哦！",
            "够了够了！",
        ]

        # ─── 醒来对话 ───

        self._after_wake_lines = [
            "嗯...你还在呀。",
            "睡得真舒服~",
            "做了个好梦！",
            "伸个懒腰~",
        ]

        # ─── 连续互动对话 ───

        self._frequent_interaction_lines = [
            "你今天特别关注我呢~",
            "好开心你一直在！",
            "最喜欢和你玩了！",
        ]

    # ─── 基础获取方法 ───

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

    # ─── 上下文获取方法 ───

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

    def get_morning_line(self) -> str:
        return random.choice(self._morning_lines)

    def get_afternoon_line(self) -> str:
        return random.choice(self._afternoon_lines)

    def get_evening_line(self) -> str:
        return random.choice(self._evening_lines)

    def get_night_line(self) -> str:
        return random.choice(self._night_lines)

    def get_late_night_line(self) -> str:
        return random.choice(self._late_night_lines)

    # ─── 情感获取方法 ───

    def get_happy_line(self) -> str:
        return random.choice(self._happy_lines)

    def get_sleepy_line(self) -> str:
        return random.choice(self._sleepy_lines)

    def get_energetic_line(self) -> str:
        return random.choice(self._energetic_lines)

    def get_bored_line(self) -> str:
        return random.choice(self._bored_lines)

    # ─── 特殊获取方法 ───

    def get_repeat_click_line(self, count: int = 1) -> str:
        """根据连续点击次数返回对话。

        Args:
            count: 连续点击次数
        """
        if count >= 5:
            return random.choice(self._repeat_click_lines[-2:])
        elif count >= 3:
            return random.choice(self._repeat_click_lines[-3:])
        else:
            return random.choice(self._click_lines)

    def get_after_wake_line(self) -> str:
        return random.choice(self._after_wake_lines)

    def get_frequent_interaction_line(self) -> str:
        return random.choice(self._frequent_interaction_lines)
