# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


block_cipher = None

pymorphy_datas = collect_data_files("pymorphy3_dicts_ru")

app_hiddenimports = collect_submodules("app") + [
    "pymorphy3",
    "pymorphy3.analyzer",
    "pymorphy3.units",
    "dawg2_python",
    "pymorphy3_dicts_ru",
]

a = Analysis(
    ["app/main.py"],
    pathex=[],
    binaries=[],
    datas=[("app/i18n/*.json", "app/i18n"), *pymorphy_datas],
    hiddenimports=app_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="DocuFindLocal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

