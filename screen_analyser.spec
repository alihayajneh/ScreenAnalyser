# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Screen Analyser
# Build:  venv\Scripts\pyinstaller screen_analyser.spec

from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ['screen_analyser.pyw'],
    pathex=['.'],          # project root — so `import app` resolves
    binaries=[],
    datas=[
        ('icon.ico', '.'),  # bundled asset; loaded via config.resource_path()
    ],
    hiddenimports=[
        # All app sub-modules (auto-collected but listed explicitly for safety)
        *collect_submodules('app'),
        # pystray Windows backend
        'pystray._win32',
        # keyboard hooks
        'keyboard',
        # ollama / httpx internals not always auto-detected
        'anyio._backends._asyncio',
        'anyio._backends._trio',
        'httpx',
        'httpcore',
        # RTL / Arabic text rendering
        'arabic_reshaper',
        'bidi',
        'bidi.algorithm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # trim fat we don't use
        'matplotlib', 'numpy', 'pandas', 'scipy',
        'unittest', 'doctest', 'pdb',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name          = 'ScreenAnalyser',
    debug         = False,
    bootloader_ignore_signals = False,
    strip         = False,
    upx           = True,       # shrinks the exe if UPX is on PATH; safe to leave True
    upx_exclude   = [],
    runtime_tmpdir= None,
    console       = False,      # no black console window (equivalent to .pyw)
    disable_windowed_traceback = False,
    argv_emulation = False,
    target_arch   = None,
    codesign_identity = None,
    entitlements_file = None,
    icon          = 'icon.ico', # exe file icon (shown in Explorer)
    onefile       = True,       # single self-contained .exe
)
