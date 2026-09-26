@echo off
chcp 65001 >nul
setlocal EnableExtensions
title GBC Nina 打包

cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

REM 检查虚拟环境
if not exist "%VENV_PY%" (
    echo [错误] 未找到虚拟环境，请先运行 run.bat 创建
    goto :error
)

REM 安装 PyInstaller
echo [信息] 确保 PyInstaller 已安装...
"%VENV_PY%" -m pip install pyinstaller --disable-pip-version-check -q
if errorlevel 1 (
    echo [错误] PyInstaller 安装失败
    goto :error
)

REM 打包
echo [信息] 开始打包...
"%VENV_PY%" -m PyInstaller ^
    --onedir ^
    --name "GBC Nova" ^
    --icon app.ico ^
    --windowed ^
    --add-data "bin/sense-voice-main.exe;bin" ^
    --add-data "bin/libdl.dll;bin" ^
    --add-data "models/sense-voice-small-q8_0.gguf;models" ^
    --add-data "config/default.json;config" ^
    --hidden-import PySide6 ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    --clean ^
    main.py

if errorlevel 1 (
    echo [错误] 打包失败
    goto :error
)

echo.
echo [成功] 打包完成！输出目录: dist\GBC Nova\
echo        可直接运行 dist\GBC Nova\GBC Nova.exe

REM --add-data 把资源放到 _internal\，需要复制到顶层供程序相对路径找到
echo [信息] 复制资源文件到顶层...
if exist "dist\GBC Nova\_internal\bin" (
    xcopy /Y /Q "dist\GBC Nova\_internal\bin\*.*" "dist\GBC Nova\bin\" >nul 2>&1
)
if exist "dist\GBC Nova\_internal\models" (
    xcopy /Y /Q "dist\GBC Nova\_internal\models\*.*" "dist\GBC Nova\models\" >nul 2>&1
)
if exist "dist\GBC Nova\_internal\config" (
    xcopy /Y /Q "dist\GBC Nova\_internal\config\*.*" "dist\GBC Nova\config\" >nul 2>&1
)

goto :end

:error
echo.
echo 打包失败，请检查以上错误信息
pause
exit /b 1

:end
endlocal
