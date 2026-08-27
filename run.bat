@echo off
REM GBC Nina 启动脚本
REM 自动使用虚拟环境运行

cd /d "%~dp0"
call .venv\Scripts\activate.bat
python main.py
