# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['main']
hiddenimports += collect_submodules('app.database')


a = Analysis(
    ['launcher.py'],
    pathex=['.venv\\Lib\\site-packages', '.venv\\Lib\\site-packages\\win32', '.venv\\Lib\\site-packages\\win32\\lib', '.venv\\Lib\\site-packages\\Pythonwin'],
    binaries=[('.venv\\Lib\\site-packages\\psycopg2_binary.libs\\libpq-29b01d8382d5824098bc0b4861813b70.dll', '.'), ('.venv\\Lib\\site-packages\\psycopg2_binary.libs\\libcrypto-3-x64-e57e1a41cc5d7f9b741c935f04fe4f2f.dll', '.'), ('.venv\\Lib\\site-packages\\psycopg2_binary.libs\\libssl-3-x64-6b7807fd98efdd91c677351cd0a9f2d8.dll', '.')],
    datas=[('logging.yaml', '.'), ('.env.example', '.'), ('settings.yaml.example', '.'), ('frontend\\dist', 'frontend\\dist'), ('app\\screen_snippets', 'app\\screen_snippets')],
    hiddenimports=hiddenimports,
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
    name='STFCRepTracker',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='STFCRepTracker',
)
