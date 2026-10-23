"""Mantiene visible la gráfica UE para detectar bloqueos y cierres nativos de Qt."""

import os
import subprocess
import sys

import pytest

WINDOW_SCRIPT = """
import os
import sys
import traceback

if os.name == "posix":
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QScrollArea

from macronet.application import MainWindow

app = QApplication([])
window = MainWindow()
window.appearance.set_mode(sys.argv[1])
tabs = window.centralWidget()
assignment = tabs.widget(4)
assignment.method_selector.setCurrentIndex(1)
assignment.calculate(raise_errors=True)
expected_result = assignment.current_result
assert expected_result.method == "ue" and expected_result.history
canvas = assignment.history_canvas
scroll = assignment.findChild(QScrollArea)
samples = []

def report_failure(exc_type, error, tb):
    traceback.print_exception(exc_type, error, tb)
    app.exit(1)

sys.excepthook = report_failure

def show_history():
    assignment.results_tabs.setCurrentWidget(canvas)
    scroll.ensureWidgetVisible(canvas)

def show_network():
    assignment.results_tabs.setCurrentWidget(assignment.network_canvas.parentWidget())
    scroll.ensureWidgetVisible(assignment.network_canvas)

def resize_small():
    window.resize(1000, 750)
    show_history()

def resize_and_change_theme():
    window.resize(1440, 1000)
    window.appearance.set_mode("dark" if sys.argv[1] == "light" else "light")

def finish():
    # El temporizador debe seguir ejecutándose y el tamaño debe estabilizarse.
    assert len(samples) >= 8, samples
    assert len(set(samples[-4:])) == 1, samples[-4:]
    assert 100 < canvas.height() < 2 * window.height(), samples
    assert assignment.current_result is expected_result
    line = canvas.figure.axes[0].lines[0]
    assert list(line.get_xdata()) == [item.number for item in expected_result.history]
    assert list(line.get_ydata()) == [item.relative_gap for item in expected_result.history]
    print("UE window responsive; layout stable; history preserved", flush=True)
    app.exit(0)

window.show()
tabs.setCurrentIndex(4)
show_history()
heartbeat = QTimer()
heartbeat.timeout.connect(lambda: samples.append((canvas.width(), canvas.height())))
heartbeat.start(50)
QTimer.singleShot(400, show_network)
QTimer.singleShot(700, resize_small)
QTimer.singleShot(1000, resize_and_change_theme)
QTimer.singleShot(2200, finish)
exit_code = app.exec()
window._dirty = False
window.close()
sys.exit(exit_code)
"""


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_ue_convergence_window_stays_responsive(theme):
    # Un fallo nativo o un bloqueo deben fallar esta prueba sin cerrar todo pytest.
    result = subprocess.run(
        [sys.executable, "-c", WINDOW_SCRIPT, theme],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "UE window responsive; layout stable; history preserved" in result.stdout
