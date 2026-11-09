# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, get_package_paths

hiddenimports = ['main']
hiddenimports += collect_submodules('app.database')

# ai: claude-opus-5-5 | 2026-11-09
# torchvision loads its compiled ops with torch.ops.load_library(<path next to its __file__>),
# not an import, so PyInstaller can't see them. The contrib hook still asks for the old
# 'torchvision._C' name; since 0.29 the files are _C_stable.pyd / image_stable.pyd, and without
# them the frozen app dies at import with "operator torchvision::nms does not exist".
# Take every extension and DLL in the package folder so the next rename can't drop them silently.
_, _torchvision_dir = get_package_paths('torchvision')
torchvision_binaries = [
    (str(path), 'torchvision')
    for pattern in ('*.pyd', '*.dll')
    for path in Path(_torchvision_dir).glob(pattern)
]
assert any(Path(binary[0]).name.startswith('_C') for binary in torchvision_binaries), (
    f"No torchvision _C*.pyd ops extension found in {_torchvision_dir}; nms and OCR would fail at runtime."
)


a = Analysis(
    ['launcher.py'],
    pathex=['.venv\\Lib\\site-packages', '.venv\\Lib\\site-packages\\win32', '.venv\\Lib\\site-packages\\win32\\lib', '.venv\\Lib\\site-packages\\Pythonwin'],
    # ai: claude-opus-5-5 | 2026-11-07
    # psycopg2's bundled DLLs (psycopg2_binary.libs) are found by PyInstaller's own hooks;
    # listing them here pinned hashed file names that change with every psycopg2 release.
    binaries=torchvision_binaries,
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
