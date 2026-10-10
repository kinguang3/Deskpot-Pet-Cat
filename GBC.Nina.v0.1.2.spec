# -*- mode: python ; coding: utf-8 -*-

import os

# config/ 目录逐文件收录，只打包 default.json。
# 绝不能整目录拷贝：config/user.json 是开发者本机的真实配置
# （含本机调过的 behavior 时长、自定义语音指令），一旦打进包里，
# 所有下载用户首次启动都会 merge 继承开发者的个性化配置。
# user.json 由程序在用户首次保存设置时于运行目录生成。
_datas = [
    ('assets', 'assets'),
    ('config/default.json', 'config'),
    ('models', 'models'),
]

_user_cfg = os.path.join('config', 'user.json')
if os.path.exists(_user_cfg):
    print(
        '[spec] 提示: 已跳过 %s（开发者本机配置，不应分发）' % _user_cfg
    )

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('bin', 'bin')],
    datas=_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GBC.Nina.v0.1.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GBC.Nina.v0.1.2',
)
