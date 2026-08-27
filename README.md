# GBC Nina

一只住在你桌面上的小猫。

Nina 是一款轻量级 Windows 桌面宠物，她会陪伴你工作、学习，有自己的情绪和行为节奏。

## 功能特性

- **透明无边框窗口** — 始终显示在桌面，不影响其他程序
- **流畅动画系统** — 待机、行走、睡觉、打字、注视等多种动画
- **自主行为** — 随机走动、停留、睡觉，有自己的节奏
- **鼠标互动** — 单击、双击、拖动都有反应
- **对话气泡** — 根据时间、状态、交互显示不同台词
- **系统托盘** — 显示/隐藏/设置/退出
- **设置面板** — 调整大小、透明度、行为开关

## 系统要求

- Windows 10/11
- Python 3.10+

## 安装与运行

```bash
# 克隆仓库
git clone https://github.com/kinguang3/Deskpot-Pet-Cat.git
cd Deskpot-Pet-Cat

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

或直接双击 `run.bat`。

## 使用方法

| 操作 | 效果 |
|------|------|
| 拖动 | 移动 Nina 的位置 |
| 单击 | Nina 会看你一眼并说话 |
| 双击 | 触发特殊动画 |
| 右键 | 显示对话 |
| 右下角猫爪图标 | 打开菜单（显示/隐藏/设置/退出） |
| 长时间不互动 | Nina 会自己睡着 |

## 项目结构

```
GBC-Nina/
├── main.py                 # 程序入口
├── run.bat                 # 一键启动
├── requirements.txt        # 依赖
├── config/                 # 配置
│   └── default.json
├── assets/                 # 精灵图资源
│   ├── cat_idle*.png       # 待机动画 (8帧)
│   ├── cat_walk_*.png      # 行走动画 (左右各8帧)
│   ├── cat_typing*.png     # 打字动画 (8帧)
│   ├── cat_watching*.png   # 注视动画 (8帧)
│   ├── cat_sleep*.png      # 睡觉动画 (2帧)
│   └── cat_*.png           # 特殊状态图
└── src/
    ├── app.py              # 应用管理器
    ├── core/               # 核心模块
    │   ├── window.py       # 透明窗口
    │   ├── pet.py          # 宠物实体
    │   ├── event_bus.py    # 事件总线
    │   └── config.py       # 配置管理
    ├── animation/          # 动画系统
    ├── behavior/           # 行为状态机
    ├── interaction/        # 鼠标交互
    ├── dialogue/           # 对话系统
    ├── ui/                 # 界面组件
    └── utils/              # 工具类
```

## 技术栈

- **Python 3.12**
- **PySide6** — Qt for Python，提供透明窗口、动画、系统托盘支持

## 开发说明

```bash
# 仅安装依赖，不运行
pip install -r requirements.txt

# 运行测试
python -c "from src.animation.sprites import SpriteLoader; SpriteLoader().load_all()"
```

## 许可证

MIT License
