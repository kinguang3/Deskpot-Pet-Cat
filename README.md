# GBC Nina

> **目录**
>
> - [一、项目简介](#一项目简介)
> - [二、功能特性](#二功能特性)
> - [三、依赖项](#三依赖项)
> - [四、快速开始](#四快速开始)
> - [五、使用说明](#五使用说明)
> - [六、项目结构](#六项目结构)
> - [七、技术架构](#七技术架构)
> - [八、编码规范](#八编码规范)
> - [九、FAQ](#九faq)
> - [十、贡献指南](#十贡献指南)
> - [十一、许可证](#十一许可证)
> - [十二、联系方式](#十二联系方式)

一只住在你桌面上的小猫。

GBC Nina 是一款轻量级 Windows 桌面宠物，基于 Python + PySide6 构建。她会陪伴你工作、学习，有自己的情绪和行为节奏——安静但好奇，偶尔主动，大部分时间自处。

> **当前状态**: v0.1.0，已实现透明窗口、动画播放、自主行为、鼠标交互、对话气泡、系统托盘、设置面板、语音情绪识别、自定义语音指令等核心功能。

---

## 一、项目简介

GBC Nina 的核心目标是提供一个 **有生命感** 的桌面伴侣，而不是一个简单的动画播放器。

项目采用 **Python + PySide6** 实现，整体架构如下：

- **核心层 (core)**: 透明窗口管理、宠物实体、事件总线（模块间通信）、配置管理。
- **动画层 (animation)**: 精灵图加载器 + 动画管理器，支持多动画切换、帧率控制、循环/单次播放。
- **行为层 (behavior)**: 有限状态机引擎 + 情感系统，管理 Nina 的自主行为决策和情绪变化。
- **交互层 (interaction)**: 鼠标事件处理，将原始输入转化为语义化事件（单击、双击、悬停、拖动）。
- **对话层 (dialogue)**: 气泡 UI + 内容管理器，根据时间、状态、交互事件、语音情绪动态选择对话内容。
- **语音层 (voice)**: 麦克风采集 → VAD 分段 → 语音识别 → 情绪分析 → 指令执行。
- **界面层 (ui)**: 系统托盘、设置面板（含语音指令管理）。
- **工具层 (utils)**: JSON 数据持久化存储。

模块间通过 **事件总线 (EventBus)** 解耦通信，不直接引用彼此，便于扩展和维护。

---

## 二、功能特性

- **透明无边框窗口** — 无边框、透明背景、始终置顶、不在任务栏显示，可自由拖动。

- **动画系统** — 支持 7 种动画（idle / walk_left / walk_right / typing / typing_red / watching / sleep），每种动画独立帧率，支持循环和单次播放。

- **行为状态机** — 通用有限状态机引擎，定义 7 种行为状态，状态间通过条件自动转换，支持优先级和用户行为打断。

- **情感系统** — 管理 Nina 的内部情感状态（精力、快乐、好奇心、困倦、依恋），影响行为权重，用户交互和语音情绪都会改变情感值。

- **鼠标交互** — 支持单击、双击、右键、拖动、鼠标悬停、长时间无交互检测。

- **对话气泡** — 圆角气泡 + 三角尾巴，根据时间、状态、交互事件、语音情绪动态选择对话内容。

- **系统托盘** — 猫爪图标，右键菜单支持显示/隐藏/设置/退出。

- **设置面板** — 可调整窗口大小、透明度、置顶、自动移动、对话开关，以及语音指令管理。

- **语音情绪识别（Hybrid 双 Provider）** — AssemblyAI 负责高质量转录与英语情绪，SenseVoice 负责中文情绪、语种识别与事件检测，两者并行执行并按语言合并结果，支持单 Provider 降级。

- **语音情绪响应** — 用户说话时，Nina 会识别你的情绪并做出反应：你开心她也开心，你难过她会安慰你。

- **自定义语音指令** — 用户可通过设置面板自定义唤醒词和语音指令，支持打开网站、显示时间、播放动画等动作。

---

## 三、依赖项

### 1. 系统要求

| 项目     | 要求                       |
| -------- | -------------------------- |
| 操作系统 | Windows 10/11              |
| Python   | 3.10 或更高版本            |
| 磁盘空间 | ~50 MB（含本地语音模型）   |

### 2. Python 包依赖

| 包名        | 版本     | 用途                                            |
| ----------- | -------- | ----------------------------------------------- |
| PySide6     | >= 6.5.0 | Qt for Python，提供透明窗口、动画、系统托盘支持 |
| assemblyai  | >= 1.5.4 | AssemblyAI 的官方 Python SDK                    |
| numpy       | ==2.4.4  | 数学函数、音频处理                              |
| sounddevice | >= 0.4.6 | 麦克风音频采集                                  |
| python-dotenv | >= 1.0.0 | 环境变量管理                                  |

安装命令：

```bash
pip install -r requirements.txt
```

> **注意**: 建议使用虚拟环境（`.venv`），避免污染全局 Python 环境。

---

## 四、快速开始

### 1. 获取源码

```bash
git clone https://github.com/kinguang3/Deskpot-Pet-Cat.git
cd Deskpot-Pet-Cat
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（Windows PowerShell）
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置 API Key（可选）

如果需要使用 AssemblyAI 云端语音识别，在项目根目录创建 `.env` 文件：

```
ASSEMBLYAI_API_KEY=your_api_key_here
```

> 不配置 API Key 也可以运行，将使用纯本地 SenseVoice 模型。

### 4. 运行

```bash
# 方式一：命令行
python main.py

# 方式二：双击 run.bat（自动使用虚拟环境）
```

启动后，Nina 会出现在屏幕底部中间位置，播放 idle 动画。

---

## 五、使用说明

### 1. 鼠标操作

| 操作             | 效果                              |
| ---------------- | --------------------------------- |
| **拖动**         | 移动 Nina 的位置                  |
| **单击**         | Nina 会看你一眼并说话             |
| **双击**         | 触发特殊动画（typing / watching） |
| **右键**         | 显示对话                          |
| **鼠标悬停**     | 30% 概率显示对话                  |
| **长时间不互动** | Nina 会自己睡着                   |

### 2. 系统托盘

右下角猫爪图标，右键菜单：

| 菜单项    | 功能                 |
| --------- | -------------------- |
| 显示 Nina | 显示窗口并居中到底部 |
| 隐藏 Nina | 隐藏窗口             |
| 设置      | 打开设置面板         |
| 退出      | 关闭程序             |

双击托盘图标 = 显示窗口。

### 3. 设置面板

| 设置项   | 范围       | 默认值 | 说明                 |
| -------- | ---------- | ------ | -------------------- |
| 大小     | 50% ~ 200% | 100%   | 窗口缩放比例         |
| 透明度   | 30% ~ 100% | 95%    | 窗口透明度           |
| 始终置顶 | 开/关      | 开     | 窗口是否始终在最上层 |
| 自动移动 | 开/关      | 开     | Nina 是否自主走动    |
| 显示对话 | 开/关      | 开     | 是否显示对话气泡     |

设置修改后点击"保存"立即生效，配置持久化到 `config/user.json`。

### 4. 对话系统

Nina 的对话根据以下条件动态选择：

- **时间段**: 早晨/下午/晚上/深夜各有不同台词
- **交互事件**: 点击、拖动、悬停触发不同反应
- **语音情绪**: 听到你开心/难过/生气时做出反应
- **空闲状态**: 随机显示自言自语
- **睡眠状态**: 显示睡觉相关台词

对话间隔 30~60 秒随机，避免频繁打扰。

### 5. 语音情绪识别

语音模块支持三种 provider：

| provider   | 定位       | 能力                                   |
| ---------- | ---------- | -------------------------------------- |
| `assemblyai` | 云端     | 高质量转录、英语情绪分析               |
| `sensevoice` | 本地 GGUF | 中文情绪、语种识别、音频事件检测       |
| `hybrid`   | 组合（推荐）| 两者并行，按语言合并结果              |

`hybrid` 模式下，AssemblyAI 与 SenseVoice 并行处理同一段音频，再按语言合并：

- **文本**优先 AssemblyAI，为空时用 SenseVoice
- **语言**优先 SenseVoice，失败时退回 AssemblyAI
- **情绪**在语言为 `en` 且 AssemblyAI 情绪有效时用 AssemblyAI，否则用 SenseVoice

### 6. 语音情绪响应

用户说话时，Nina 会识别情绪并做出反应：

| 用户情绪 | Nina 反应                | 情感变化           |
| -------- | ------------------------ | ------------------ |
| HAPPY    | 显示快乐台词             | 快乐 +3~8          |
| SAD      | 显示安慰台词             | 快乐 -3, 依恋 +2  |
| ANGRY    | 显示冷静台词             | 快乐 -2            |
| NEUTRAL  | 轻微好奇                 | 好奇心 +0.5        |

### 7. 自定义语音指令

#### 唤醒词

默认唤醒词：`hey nina`、`小猫`、`nina`

说唤醒词后，Nina 进入聆听模式（5秒），等待你的指令。

#### 预设指令

| 触发词   | 动作        | 说明         |
| -------- | ----------- | ------------ |
| 几点了   | show_time   | 显示当前时间 |
| 今天几号 | show_date   | 显示当前日期 |
| 早上好   | show_greeting | 显示问候语 |
| 开心     | play_happy  | 播放开心动画 |
| 跳舞     | play_dance  | 播放跳舞动画 |
| 状态     | show_status | 显示状态信息 |

#### 添加自定义指令

1. 右键托盘图标 → 设置
2. 在"语音指令"区域点击"添加"
3. 输入触发词（如"打开百度"）
4. 选择动作类型（如"open_website"）
5. 输入网址（如"baidu.com"）
6. 点击"保存"

支持的动作类型：

| 动作           | 说明             |
| -------------- | ---------------- |
| show_time      | 显示时间         |
| show_date      | 显示日期         |
| show_greeting  | 显示问候语       |
| play_happy     | 播放开心动画     |
| play_dance     | 播放跳舞动画     |
| show_status    | 显示状态信息     |
| show_dialogue  | 显示自定义对话   |
| open_website   | 打开网站         |

---

## 六、项目结构

<details>
<summary>点击展开目录树</summary>

```
GBC-Nina/
├── main.py                        # 程序入口
├── run.bat                        # 一键启动（cmd）
├── requirements.txt               # Python 依赖
├── README.md                      # 项目说明文档
│
├── docs/                          # 文档目录
│   └── voice.md                   # 语音情绪识别模块说明
│
├── config/                        # 配置文件目录
│   └── default.json               # 默认配置
│
├── assets/                        # 精灵图资源（54张PNG）
│   ├── cat_idle1-8.png            # 待机动画 (8帧)
│   ├── cat_walk_left1-8.png       # 向左行走动画 (8帧)
│   ├── cat_walk_right1-8.png      # 向右行走动画 (8帧)
│   ├── cat_typing1-8.png          # 打字动画 (8帧)
│   ├── cat_typing_red1-8.png      # 打字变体-红色 (8帧)
│   ├── cat_watching1-8.png        # 注视动画 (8帧)
│   └── cat_sleep1-2.png           # 睡觉动画 (2帧)
│
├── bin/                           # 语音推理引擎
│   └── sense-voice-main.exe       # SenseVoice 本地推理
│
├── models/                        # 语音模型
│   ├── sense-voice-small-q8_0.gguf # SenseVoice 模型
│   └── fsmn-vad.gguf              # VAD 模型
│
└── src/                           # 源代码
    ├── __init__.py
    ├── app.py                     # 应用管理器（核心协调器）
    │
    ├── core/                      # 核心模块
    │   ├── config.py              # 配置管理
    │   ├── event_bus.py           # 事件总线
    │   ├── window.py              # 透明窗口
    │   └── pet.py                 # 宠物实体
    │
    ├── animation/                 # 动画系统
    │   ├── sprites.py             # 精灵图加载器
    │   └── manager.py             # 动画管理器
    │
    ├── behavior/                  # 行为系统
    │   ├── state_machine.py       # 有限状态机
    │   ├── states.py              # 行为状态定义
    │   ├── emotion.py             # 情感系统
    │   ├── scheduler.py           # 行为调度器
    │   ├── controller.py          # 行为控制器
    │   └── memory.py              # 记忆系统
    │
    ├── interaction/               # 交互系统
    │   └── mouse.py               # 鼠标交互
    │
    ├── dialogue/                  # 对话系统
    │   ├── bubble.py              # 对话气泡UI
    │   └── content.py             # 对话内容管理
    │
    ├── ui/                        # 界面组件
    │   ├── tray.py                # 系统托盘
    │   └── settings.py            # 设置面板
    │
    ├── voice/                     # 语音系统
    │   ├── audio_capture.py       # 麦克风采集
    │   ├── audio_segmenter.py     # VAD 音频分段
    │   ├── emotion_parser.py      # 情绪标签归一化
    │   ├── voice_manager.py       # 语音模块入口
    │   ├── commands.py            # 语音指令管理
    │   └── providers/             # 语音提供方
    │       ├── base.py                    # 抽象接口
    │       ├── assemblyai_provider.py     # 云端转录
    │       ├── sensevoice_gguf_provider.py # 本地中文
    │       └── hybrid_provider.py         # 双 Provider 协同
    │
    └── utils/                     # 工具类
        └── storage.py             # JSON数据持久化
```

</details>

---

## 七、技术架构

### 1. 模块通信：事件驱动

模块间不直接引用，通过 EventBus 发送/监听事件：

```
用户操作 → Interaction → EventBus → Behavior(决策) → Animation(播放)
                                  ↓
                             EmotionSystem(情感)
                                  ↓
                             Dialogue(显示对话)

语音输入 → VoiceManager → EventBus → EmotionSystem(情感更新)
                                   → CommandManager(指令执行)
                                   → Dialogue(显示反应)
```

### 2. 行为系统：有限状态机 + 情感系统

```
情感值（精力/快乐/好奇心/困倦/依恋）
    ↓ 影响权重
[Idle] ──随机走动──→ [Walk] ──到达目标──→ [Idle]
  │                                        ↑
  │──长时间无操作──→ [Sleep] ──被点击──→ [Idle]
  │
  │──用户点击──→ [Clicked] ──1.5秒后──→ [Idle]
  │
  │──鼠标悬停──→ [Watch] ──3秒后──→ [Idle]
```

### 3. 语音系统：双 Provider 并行

```
麦克风 → AudioCapture → AudioSegmenter(VAD) → 并行处理
                                                ↓
                                    ┌───────────┴───────────┐
                                    │                       │
                              AssemblyAI               SenseVoice
                              (云端转录)               (本地推理)
                                    │                       │
                                    └───────────┬───────────┘
                                                ↓
                                    HybridVoiceProvider(合并)
                                                ↓
                                    EmotionParser(情绪归一化)
                                                ↓
                                    CommandManager(指令检查)
                                                ↓
                                    EventBus → App(响应)
```

### 4. 窗口底层原理

```
QMainWindow + Qt.WindowFlags:
  ├─ FramelessWindowHint      # 无边框
  ├─ WindowStaysOnTopHint     # 始终置顶
  └─ Tool                     # 不显示在任务栏

WA_TranslucentBackground = True  # 透明背景
paintEvent() → QPainter 绘制精灵帧
```

---

## 八、编码规范

- **文件编码**: UTF-8
- **缩进**: 4 个空格
- **命名规则**: 类名 `PascalCase`，变量/函数名 `snake_case`，常量 `UPPER_CASE`
- **注释**: 仅在必要处添加，不过度注释
- **模块化**: 每个文件职责单一，通过 EventBus 通信
- **异常处理**: 关键操作有 try-except 保护

---

## 九、FAQ

### 运行问题

<details>
<summary><b>Q1: 启动报错 `ModuleNotFoundError`</b></summary>

**解决方案**:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

</details>

<details>
<summary><b>Q2: 窗口出现了但看不到猫咪</b></summary>

**解决方案**:

- 确认 `assets/` 目录下有完整的 PNG 文件
- 检查控制台是否有 `[SpriteLoader]` 相关日志

</details>

### 语音问题

<details>
<summary><b>Q3: 语音识别不工作</b></summary>

**可能原因**:

- 没有麦克风或麦克风权限被拒绝
- SenseVoice 模型文件缺失

**解决方案**:

- 确认麦克风已连接且权限正常
- 检查 `models/` 目录下是否有模型文件
- 查看控制台 `[Voice]` 相关日志

</details>

<details>
<summary><b>Q4: 如何添加自定义语音指令？</b></summary>

**步骤**:

1. 右键托盘图标 → 设置
2. 在"语音指令"区域点击"添加"
3. 输入触发词，选择动作类型
4. 点击"保存"

</details>

---

## 十、贡献指南

欢迎提交 Issue 和 Pull Request。在贡献前请确保：

- 代码遵循现有风格（缩进 4 空格，命名规范）
- 使用 UTF-8 编码提交代码
- 添加或修改功能时更新相关文档
- 确保本地测试通过
- 对于较大的改动，请先开 Issue 讨论

---

## 十一、许可证

本项目采用 **MIT License** 开源。

本项目依赖的第三方组件：

| 组件                    | 许可证             |
| ----------------------- | ------------------ |
| PySide6 (Qt for Python) | LGPL-3.0 / GPL-3.0 |
| assemblyai              | MIT                |

---

## 十二、联系方式

- 作者: [kinguang3](https://github.com/kinguang3)
- 作者: [CrimsonSeraph](https://github.com/CrimsonSeraph)
- 项目主页: [https://github.com/kinguang3/Deskpot-Pet-Cat](https://github.com/kinguang3/Deskpot-Pet-Cat)
