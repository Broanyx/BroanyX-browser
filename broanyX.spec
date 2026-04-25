# BroanyX Browser — PyInstaller Build Spec
# ==========================================
# Run: pyinstaller broanyX.spec --clean
#
# This produces: dist/BroanyX/BroanyX.exe  (with all dependencies)

import sys
from pathlib import Path

block_cipher = None

# Collect all source files
added_files = [
    # (source, dest_folder_in_bundle)
    ("assets/icon.ico",   "assets"),
    ("assets/icon.png",   "assets"),
    ("assets/style.qss",  "assets"),
    ("assets/onion.png",  "assets"),
    ("version.json",      "."),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtNetwork",
        "PyQt6.sip",
        "stem",
        "stem.control",
        "stem.process",
        "socks",
        "requests",
        "adblockparser",
        "updater",
        "browser_window",
        "tab_widget",
        "web_view",
        "adblocker",
        "privacy_settings",
        "tor_manager",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BroanyX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window — pure GUI app
    icon="assets/icon.ico", # .exe icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BroanyX",
)
