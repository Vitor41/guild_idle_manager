# PyInstaller one-folder build. Assets, Alembic migrations, and templates remain local/offline.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parents[1]
webview_datas, webview_binaries, webview_hiddenimports = collect_all("webview")

a = Analysis(
    [str(root / "app/desktop/__main__.py")],
    pathex=[str(root)],
    binaries=webview_binaries,
    datas=[
        (str(root / "app/templates"), "app/templates"),
        (str(root / "app/static"), "app/static"),
        (str(root / "app/data"), "app/data"),
        (str(root / "alembic"), "alembic"),
        (str(root / "alembic.ini"), "."),
        *webview_datas,
    ],
    hiddenimports=webview_hiddenimports + ["webview.platforms.edgechromium"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GuildIdleManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / "app/static/assets/desktop/app-icon.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GuildIdleManager",
)
