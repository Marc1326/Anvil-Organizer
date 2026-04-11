# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Anvil Organizer

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('anvil/locales', 'anvil/locales'),
        ('anvil/styles', 'anvil/styles'),
        ('anvil/assets', 'anvil/assets'),
        ('anvil/resources', 'anvil/resources'),
        ('anvil/plugins/games', 'anvil/plugins/games'),
        ('anvil/data/shims', 'anvil/data/shims'),
    ],
    hiddenimports=[
        'PySide6.QtSvg',
        'lz4',
        'lz4.block',
        'xml',
        'xml.etree',
        'xml.etree.ElementTree',
        # Game-Plugins werden dynamisch geladen — PyInstaller sieht ihre Imports nicht
        'anvil.core.bg3_mod_installer',
        'anvil.core.lspk_parser',
        'anvil.plugins.framework_mod',
        'keyring',
        'keyring.backends',
        'keyring.backends.SecretService',
        'cryptography',
        'cryptography.fernet',
        'secretstorage',
        'jeepney',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Remove libs that break host subprocesses (xdg-open, kdialog, /bin/sh)
# when PyInstaller's LD_LIBRARY_PATH leaks into child processes.
a.binaries = [b for b in a.binaries
              if not b[0].startswith(('libreadline.', 'libtinfo.'))]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='anvil-organizer',
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
    icon='anvil/resources/logo.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='anvil-organizer',
)
