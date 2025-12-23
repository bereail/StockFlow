# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

project_dir = SPECPATH  # carpeta del .spec (raíz del proyecto)

datas = [
    # DB base
    (os.path.join(project_dir, "db.sqlite3"), "."),

    # Templates (clave)
    (os.path.join(project_dir, "templates"), "templates"),

    # Static
    (os.path.join(project_dir, "static"), "static"),

    # Fixtures
    (os.path.join(project_dir, "inventario", "fixtures", "servicios.json"), "inventario/fixtures"),
    (os.path.join(project_dir, "inventario", "fixtures", "toners.json"), "inventario/fixtures"),
]


hiddenimports = []
hiddenimports += collect_submodules("django")
hiddenimports += collect_submodules("inventario")
hiddenimports += collect_submodules("config")


a = Analysis(
    ["desktop_app.py"],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
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
    name="StockToner",
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
    name="StockToner",
)
