# -*- mode: python ; coding: utf-8 -*-

import sys

sys.path.insert(0, SPECPATH)

from appimage.linux_qt_libs import qt_platform_binaries

block_cipher = None

# Windows / macOS：空列表，不改这两边的打包结果。
qt_binaries = qt_platform_binaries()

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_binaries,
    datas=[('resources/style.qss', 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YOLOTxtMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='YOLOTxtMaker.app',
        icon=None,
        bundle_identifier='com.evilmordy.yolotxtmaker',
    )
