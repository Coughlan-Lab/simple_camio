# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/students/Library/Python/3.8/lib/python/site-packages/mediapipe/modules/hand_landmark', 'mediapipe/modules/hand_landmark/'), ('/Users/students/Library/Python/3.8/lib/python/site-packages/mediapipe/modules/palm_detection', 'mediapipe/modules/palm_detection/'), ('res', 'res/')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
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
app = BUNDLE(
    exe,
    name='CamIO.app',
    icon=None,
    bundle_identifier="camio",
    info_plist={
        'NSCameraUsageDescription': 'Camera access is required to gather information about pointed element',
    }
)
