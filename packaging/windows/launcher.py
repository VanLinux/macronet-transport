"""Entrada del ejecutable; no requiere un intérprete instalado en Windows."""

import json
import multiprocessing
import os
import sys
import traceback
from pathlib import Path


def launch():
    multiprocessing.freeze_support()
    # Esta ruta permite verificar exactamente el ejecutable instalado en CI.
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        report = Path(sys.argv[2]).resolve()
        try:
            from macronet.installation_check import check_installation

            result = check_installation(report.parent)
            result["ok"] = True
            code = 0
        except Exception:
            result = {"ok": False, "error": traceback.format_exc()}
            code = 1
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return code

    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication, QMessageBox

    try:
        # Los diálogos comienzan en una carpeta de trabajo del alumno.
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        work = Path(documents or Path.home()) / "MacroNet"
        work.mkdir(parents=True, exist_ok=True)
        os.chdir(work)
        from macronet.application import main

        return main()
    except Exception:
        detail = traceback.format_exc()
        log = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MacroNet" / "inicio.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(detail, encoding="utf-8")
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(
            None, "MacroNet Transport", f"No se pudo iniciar MacroNet.\nRegistro: {log}"
        )
        del app
        return 1


if __name__ == "__main__":
    raise SystemExit(launch())
