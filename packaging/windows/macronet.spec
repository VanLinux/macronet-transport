# PyInstaller onedir: Python/Qt separados y SUMO en su propia carpeta nativa.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
datas = collect_data_files("macronet")
datas += collect_data_files("statsmodels")
for package in ("macronet-transport", "statsmodels", "pandas", "matplotlib"):
    datas += copy_metadata(package)

a = Analysis(
    [str(root / "packaging/windows/launcher.py")],
    pathex=[str(root / "src")],
    binaries=[], datas=datas,
    hiddenimports=collect_submodules("statsmodels") + ["openpyxl", "scipy.special._ufuncs"],
    hookspath=[], hooksconfig={"matplotlib": {"backends": ["QtAgg"]}},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="MacroNet",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, icon=str(root / "build/windows/MacroNet.ico"),
    version=str(root / "build/windows/version.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="MacroNet")

