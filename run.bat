@echo off
chcp 65001 >nul
setlocal EnableExtensions
title GBC Nina 启动脚本

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=requirements.txt"
set "MAIN_FILE=main.py"

echo GBC Nina 启动脚本

REM 检查 main.py 是否存在
if not exist "%MAIN_FILE%" (
    echo [错误] 未找到 %MAIN_FILE%，请确认脚本与 main.py 在同一目录
    goto :error
)

REM 如果虚拟环境已存在，直接使用
if exist "%VENV_PY%" goto :venv_ready

echo [信息] 未检测到虚拟环境，开始创建...

REM 优先使用 python 命令
python --version >nul 2>nul
if not errorlevel 1 (
    set "BASE_PYTHON=python"
    goto :create_venv
)

REM 其次使用 py -3
py -3 --version >nul 2>nul
if not errorlevel 1 (
    set "BASE_PYTHON=py -3"
    goto :create_venv
)

echo [错误] 未检测到 Python，请先安装 Python 3，并确保 python 或 py 命令可用
goto :error

:create_venv
echo [信息] 使用 %BASE_PYTHON% 创建虚拟环境：%VENV_DIR%
%BASE_PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [错误] 创建虚拟环境失败
    goto :error
)

if not exist "%VENV_PY%" (
    echo [错误] 虚拟环境创建后未找到 %VENV_PY%
    goto :error
)

:venv_ready
echo [信息] 使用虚拟环境：%VENV_DIR%

REM 设置虚拟环境变量，方便 main.py 内部调用 python 时也使用当前虚拟环境
set "VIRTUAL_ENV=%CD%\%VENV_DIR%"
set "PATH=%CD%\%VENV_DIR%\Scripts;%PATH%"

REM 升级 pip，失败不阻塞
echo [信息] 检查/升级 pip ...
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check
if errorlevel 1 (
    echo [警告] pip 升级失败，继续执行
)

REM 安装依赖
if exist "%REQ_FILE%" (
    echo [信息] 安装/检查依赖：%REQ_FILE%
    "%VENV_PY%" -m pip install -r "%REQ_FILE%" --disable-pip-version-check
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络或 %REQ_FILE%
        goto :error
    )
) else (
    echo [警告] 未找到 %REQ_FILE%，跳过依赖安装
)

REM 启动 main.py，并传递 run.bat 收到的参数
echo [信息] 启动 %MAIN_FILE% ...
"%VENV_PY%" "%MAIN_FILE%" %*
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo [错误] %MAIN_FILE% 运行结束，退出码：%EXIT_CODE%
    goto :error
)

echo [信息] %MAIN_FILE% 已正常结束
endlocal
exit /b 0

:error
echo.
echo 启动失败，请检查以上错误信息
pause
endlocal
exit /b 1
