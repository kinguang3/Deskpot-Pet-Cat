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

> **当前状态**: v0.1.0，已实现透明窗口、动画播放、自主行为、鼠标交互、对话气泡、系统托盘、设置面板等核心功能。

---

## 一、项目简介

GBC Nina 的核心目标是提供一个 **有生命感** 的桌面伴侣，而不是一个简单的动画播放器。

项目采用 **Python + PySide6** 实现，整体架构如下：

- **核心层 (core)**: 透明窗口管理、宠物实体、事件总线（模块间通信）、配置管理。
- **动画层 (animation)**: 精灵图加载器 + 动画管理器，支持多动画切换、帧率控制、循环/单次播放。
- **行为层 (behavior)**: 有限状态机引擎，管理 Nina 的自主行为决策（idle → walk → sleep 等状态转换）。
- **交互层 (interaction)**: 鼠标事件处理，将原始输入转化为语义化事件（单击、双击、悬停、拖动）。
- **对话层 (dialogue)**: 气泡 UI + 内容管理器，根据时间、状态、交互事件动态选择对话内容。
- **界面层 (ui)**: 系统托盘、设置面板。
- **工具层 (utils)**: JSON 数据持久化存储。

模块间通过 **事件总线 (EventBus)** 解耦通信，不直接引用彼此，便于扩展和维护。

---

## 二、功能特性

- **透明无边框窗口** — 无边框、透明背景、始终置顶、不在任务栏显示，可自由拖动。

- **动画系统** — 支持 7 种动画（idle / walk_left / walk_right / typing / typing_red / watching / sleep），每种动画独立帧率，支持循环和单次播放，通过 EventBus 广播动画状态变化。

- **行为状态机** — 通用有限状态机引擎，定义 7 种行为状态（idle / walk / sleep / watch / typing / clicked / dragged），状态间通过条件自动转换，支持优先级和用户行为打断。

- **鼠标交互** — 支持单击、双击、右键、拖动、鼠标悬停、长时间无交互检测，将原始输入转化为语义化事件。

- **对话气泡** — 圆角气泡 + 三角尾巴，根据当前时间（早/中/晚/深夜）、Nina 状态、用户行为动态选择对话内容，支持定时随机对话。

- **系统托盘** — 猫爪图标，右键菜单支持显示/隐藏/设置/退出，双击图标显示窗口。

- **设置面板** — 可调整窗口大小（50%~200%）、透明度（30%~100%）、始终置顶、自动移动、对话开关。

- **配置管理** — 支持默认配置 + 用户配置覆盖，JSON 格式持久化。

- **事件驱动架构** — 模块间通过 EventBus 发送/监听事件通信，松耦合易扩展。

---

## 三、依赖项

### 1. 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 |
| Python | 3.10 或更高版本 |
| 磁盘空间 | ~10 MB（不含 Python 环境） |

### 2. Python 包依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| PySide6 | >= 6.5.0 | Qt for Python，提供透明窗口、动画、系统托盘支持 |

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

### 3. 运行

```bash
# 方式一：命令行
python main.py

# 方式二：双击 run.bat（自动使用虚拟环境）
```

启动后，Nina 会出现在屏幕底部中间位置，播放 idle 动画。

---

## 五、使用说明

### 1. 鼠标操作

| 操作 | 效果 |
|------|------|
| **拖动** | 移动 Nina 的位置 |
| **单击** | Nina 会看你一眼并说话 |
| **双击** | 触发特殊动画（typing / watching） |
| **右键** | 显示对话 |
| **鼠标悬停** | 30% 概率显示对话 |
| **长时间不互动** | Nina 会自己睡着 |

### 2. 系统托盘

右下角猫爪图标，右键菜单：

| 菜单项 | 功能 |
|--------|------|
| 显示 Nina | 显示窗口并居中到底部 |
| 隐藏 Nina | 隐藏窗口 |
| 设置 | 打开设置面板 |
| 退出 | 关闭程序 |

双击托盘图标 = 显示窗口。

### 3. 设置面板

| 设置项 | 范围 | 默认值 | 说明 |
|--------|------|--------|------|
| 大小 | 50% ~ 200% | 100% | 窗口缩放比例 |
| 透明度 | 30% ~ 100% | 95% | 窗口透明度 |
| 始终置顶 | 开/关 | 开 | 窗口是否始终在最上层 |
| 自动移动 | 开/关 | 开 | Nina 是否自主走动 |
| 显示对话 | 开/关 | 开 | 是否显示对话气泡 |

设置修改后点击"保存"立即生效，配置持久化到 `config/user.json`。

### 4. 对话系统

Nina 的对话根据以下条件动态选择：

- **时间段**: 早晨/下午/晚上/深夜各有不同台词
- **交互事件**: 点击、拖动、悬停触发不同反应
- **空闲状态**: 随机显示自言自语
- **睡眠状态**: 显示睡觉相关台词

对话间隔 30~60 秒随机，避免频繁打扰。

---

## 六、项目结构

<details>
<summary>点击展开目录树</summary>

```
GBC-Nina/
├── main.py                        # 程序入口
├── run.bat                        # 一键启动（cmd）
├── run.ps1                        # 一键启动（PowerShell）
├── requirements.txt               # Python 依赖
├── README.md                      # 项目说明文档
│
├── config/                        # 配置文件目录
│   └── default.json               # 默认配置
│
├── assets/                        # 精灵图资源（54张PNG）
│   ├── cat_idle1-8.png            # 待机动画 (8帧, 165x138)
│   ├── cat_walk_left1-8.png       # 向左行走动画 (8帧)
│   ├── cat_walk_right1-8.png      # 向右行走动画 (8帧)
│   ├── cat_typing1-8.png          # 打字动画 (8帧)
│   ├── cat_typing_red1-8.png      # 打字变体-红色 (8帧)
│   ├── cat_watching1-8.png        # 注视动画 (8帧)
│   ├── cat_sleep1-2.png           # 睡觉动画 (2帧)
│   ├── cat_tall.png               # 特殊状态-拉长
│   ├── cat_long.png               # 特殊状态-伸长
│   ├── cat_melt.png               # 特殊状态-融化
│   └── cat_glitch.png             # 特殊状态-故障
│
└── src/                           # 源代码
    ├── __init__.py
    ├── app.py                     # 应用管理器（核心协调器）
    │
    ├── core/                      # 核心模块
    │   ├── __init__.py
    │   ├── config.py              # 配置管理（JSON读写、深度合并）
    │   ├── event_bus.py           # 事件总线（模块间通信）
    │   ├── window.py              # 透明窗口（无边框/置顶/拖动）
    │   └── pet.py                 # 宠物实体（位置/朝向/状态）
    │
    ├── animation/                 # 动画系统
    │   ├── __init__.py
    │   ├── sprites.py             # 精灵图加载器（按动画分组缓存）
    │   └── manager.py             # 动画管理器（帧播放/切换/循环）
    │
    ├── behavior/                  # 行为系统
    │   ├── __init__.py
    │   ├── state_machine.py       # 通用有限状态机引擎
    │   └── states.py              # 7种行为状态定义
    │
    ├── interaction/               # 交互系统
    │   ├── __init__.py
    │   └── mouse.py               # 鼠标交互（单击/双击/悬停/空闲检测）
    │
    ├── dialogue/                  # 对话系统
    │   ├── __init__.py
    │   ├── bubble.py              # 对话气泡UI（圆角/三角尾巴）
    │   └── content.py             # 对话内容管理（时间/事件感知）
    │
    ├── ui/                        # 界面组件
    │   ├── __init__.py
    │   ├── tray.py                # 系统托盘（猫爪图标）
    │   └── settings.py            # 设置面板
    │
    └── utils/                     # 工具类
        ├── __init__.py
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
                                   StateManager(更新状态)
                                        ↓
                                   Dialogue(显示对话)
```

### 2. 行为系统：有限状态机

```
[Idle] ──随机走动──→ [Walk] ──到达目标──→ [Idle]
  │                                        ↑
  │──长时间无操作──→ [Sleep] ──被点击──→ [Idle]
  │
  │──用户点击──→ [Clicked] ──1.5秒后──→ [Idle]
  │
  │──用户输入中──→ [Typing] ──停止输入──→ [Idle]
  │
  │──鼠标悬停──→ [Watch] ──3秒后──→ [Idle]
```

### 3. 动画系统：帧播放

```
SpriteLoader（加载器）         AnimationManager（管理器）
  ├─ load_animation()           ├─ play(name, loop)
  ├─ load_single()              ├─ stop() / pause() / resume()
  └─ _cache: dict               ├─ frame_changed → Signal(QPixmap)
                                └─ QTimer 控制帧率
```

### 4. 窗口底层原理

```
QMainWindow + Qt.WindowFlags:
  ├─ FramelessWindowHint      # 无边框
  ├─ WindowStaysOnTopHint     # 始终置顶
  └─ Tool                     # 不显示在任务栏

WA_TranslucentBackground = True  # 透明背景
paintEvent() → QPainter 绘制精灵帧
mousePressEvent/MoveEvent/ReleaseEvent → 拖动逻辑
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
<summary><b>Q1: 启动报错 `ModuleNotFoundError: No module named 'PySide6'`</b></summary>

**原因**: 未安装依赖或未激活虚拟环境。

**解决方案**:
```bash
# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

</details>

<details>
<summary><b>Q2: 窗口出现了但看不到猫咪</b></summary>

**可能原因**: 精灵图路径错误或资源文件缺失。

**解决方案**:
- 确认 `assets/` 目录下有完整的 PNG 文件。
- 检查控制台输出是否有 `[SpriteLoader]` 相关日志。
- 尝试手动测试精灵图加载：
```bash
python -c "from src.animation.sprites import SpriteLoader; SpriteLoader().load_all()"
```

</details>

<details>
<summary><b>Q3: 窗口出现后立即消失</b></summary>

**可能原因**: 程序启动后遇到异常退出。

**解决方案**:
- 在命令行运行 `python main.py` 查看错误输出。
- 检查是否有其他程序占用或杀毒软件拦截。

</details>

### 功能问题

<details>
<summary><b>Q4: Nina 一直站着不动</b></summary>

**可能原因**: 行为状态机未正确启动或配置中 `auto_move` 为 false。

**解决方案**:
- 检查 `config/default.json` 中 `behavior.auto_move` 是否为 `true`。
- 查看控制台是否有 `[StateMachine]` 相关日志。

</details>

<details>
<summary><b>Q5: 对话气泡不显示</b></summary>

**可能原因**: 配置中 `dialogue_enabled` 为 false，或对话内容为空。

**解决方案**:
- 检查 `config/default.json` 中 `behavior.dialogue_enabled` 是否为 `true`。
- 对话有 30~60 秒随机间隔，耐心等待或单击 Nina 触发。

</details>

<details>
<summary><b>Q6: 设置修改后不生效</b></summary>

**解决方案**:
- 修改后必须点击"保存"按钮。
- 部分设置（如大小）需要重启程序。

</details>

### 开发问题

<details>
<summary><b>Q7: 如何添加新的动画？</b></summary>

**步骤**:
1. 将动画帧 PNG 文件放入 `assets/` 目录，命名为 `cat_xxx1.png`, `cat_xxx2.png`, ...
2. 在 `src/animation/sprites.py` 的 `ANIMATION_MAP` 中添加映射：`"xxx": "cat_xxx"`
3. 在 `src/animation/manager.py` 的 `_fps_map` 中添加帧率：`"xxx": 6`
4. 在 `src/behavior/states.py` 中创建对应的状态类
5. 在 `src/behavior/state_machine.py` 中注册状态

</details>

<details>
<summary><b>Q8: 如何添加新的对话内容？</b></summary>

**步骤**:
1. 在 `src/dialogue/content.py` 的 `DialogueContent` 类中添加新的列表
2. 创建对应的 `get_xxx_line()` 方法
3. 在需要触发的地方通过 EventBus 发送事件或直接调用

</details>

---

## 十、贡献指南

欢迎提交 Issue 和 Pull Request。在贡献前请确保：

- 代码遵循现有风格（缩进 4 空格，命名规范）。
- 使用 UTF-8 编码提交代码。
- 添加或修改功能时更新相关文档。
- 确保本地测试通过（程序能正常启动和运行）。
- 对于较大的改动，请先开 Issue 讨论。

---

## 十一、许可证

本项目采用 **MIT License** 开源。

本项目依赖的第三方组件：

| 组件 | 许可证 |
|------|--------|
| PySide6 (Qt for Python) | LGPL-3.0 / GPL-3.0 |

---

## 十二、联系方式

- 作者: [kinguang3]
- GitHub: [https://github.com/kinguang3/Deskpot-Pet-Cat](https://github.com/kinguang3/Deskpot-Pet-Cat)
