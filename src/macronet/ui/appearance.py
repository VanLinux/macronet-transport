"""Apariencia neutral, tipografía Latin Modern y superficies claras/oscuras coherentes."""

from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

FONT_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "fonts"


def install_font(app):
    if app.property("macronet_font_installed"):
        return
    for path in sorted(FONT_DIRECTORY.glob("*.otf")):
        QFontDatabase.addApplicationFont(str(path))
    families = QFontDatabase.families()
    family = "Latin Modern Roman" if "Latin Modern Roman" in families else "DejaVu Serif"
    app.setFont(QFont(family, 12))
    app.setProperty("macronet_font_installed", True)


def make_scrollable(widget):
    """Conserva cada widget de etapa y sus referencias; permite pantallas pequeñas."""
    content = QWidget()
    content.setLayout(widget.layout())
    content.setMinimumWidth(850)
    scroll = QScrollArea()
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(scroll)
    for table in widget.findChildren(QTableWidget):
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(31)
        table.horizontalHeader().setMinimumSectionSize(90)
        table.horizontalHeader().setTextElideMode(Qt.TextElideMode.ElideNone)
        if table.rowCount() > 0:
            table.setMinimumHeight(115)
        table.setCornerButtonEnabled(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Evita columnas estrechas, pero permite ajustar cada una y desplazar la tabla.
        for column in range(table.columnCount()):
            header = table.horizontalHeaderItem(column)
            width = (
                QFontMetrics(table.font()).horizontalAdvance(header.text()) + 24 if header else 125
            )
            table.setColumnWidth(column, max(125, min(300, width)))


def style_figure(canvas, dark):
    background, foreground = ("#202020", "#eeeeee") if dark else ("#ffffff", "#242424")
    canvas.figure.set_facecolor(background)
    for axes in canvas.figure.axes:
        axes.set_facecolor(background)
        axes.tick_params(colors=foreground)
        for spine in axes.spines.values():
            spine.set_color(foreground)
        for label in (axes.title, axes.xaxis.label, axes.yaxis.label, *axes.texts):
            label.set_color(foreground)
        for collection in axes.collections:
            if collection.get_gid() == "network_node":
                collection.set_facecolor("#363636" if dark else "#e8e8e8")
                collection.set_edgecolor(foreground)
            else:
                collection.set_facecolor("#bbbbbb" if dark else "#505050")
        for line in axes.lines:
            line.set_color("#bbbbbb" if dark else "#505050")
        for patch in axes.patches:
            gid = patch.get_gid() or ""
            if gid.startswith("flow:"):
                ratio = float(gid.split(":")[1])
                color = (
                    ("#dddddd" if dark else "#303030")
                    if ratio > 1
                    else (("#aaaaaa" if dark else "#666666") if ratio > 0.8 else "#888888")
                )
                patch.set_color(color)
        legend = axes.get_legend()
        if legend:
            legend.get_frame().set_facecolor(background)
            for text in legend.get_texts():
                text.set_color(foreground)


class Appearance(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.mode = "auto"
        app = QApplication.instance()
        install_font(app)
        app.styleHints().colorSchemeChanged.connect(self.apply)
        self.apply()

    def set_mode(self, mode):
        self.mode = mode
        self.apply()

    def apply(self, *_args):
        app = QApplication.instance()
        dark = self.mode == "dark" or (
            self.mode == "auto" and app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        )
        self.dark = dark
        window, base, alternate, text, border, button, highlight, disabled = (
            ("#202020", "#292929", "#323232", "#ededed", "#606060", "#383838", "#555555", "#aaaaaa")
            if dark
            else (
                "#f4f4f4",
                "#ffffff",
                "#eeeeee",
                "#242424",
                "#999999",
                "#e5e5e5",
                "#d2d2d2",
                "#676767",
            )
        )
        palette = QPalette()
        for role, color in (
            (QPalette.ColorRole.Window, window),
            (QPalette.ColorRole.Base, base),
            (QPalette.ColorRole.AlternateBase, alternate),
            (QPalette.ColorRole.WindowText, text),
            (QPalette.ColorRole.Text, text),
            (QPalette.ColorRole.Button, button),
            (QPalette.ColorRole.ButtonText, text),
            (QPalette.ColorRole.Highlight, highlight),
            (QPalette.ColorRole.HighlightedText, text),
            (QPalette.ColorRole.ToolTipBase, base),
            (QPalette.ColorRole.ToolTipText, text),
            (QPalette.ColorRole.Link, text),
            (QPalette.ColorRole.PlaceholderText, disabled),
        ):
            palette.setColor(role, QColor(color))
        for role in (
            QPalette.ColorRole.Text,
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.ButtonText,
        ):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(disabled))
        app.setPalette(palette)
        app.setStyleSheet(f"""
            QMainWindow, QDialog, QTabWidget::pane {{ background: {window}; }}
            QGroupBox {{ border: 1px solid {border}; border-radius: 5px;
                        margin-top: 12px; padding: 14px 10px 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; }}
            QPushButton {{ background: {button}; color: {text}; border: 1px solid {border};
                           border-radius: 4px; padding: 6px 12px; min-height: 22px; }}
            QPushButton:hover {{ background: {highlight}; }}
            QPushButton:focus {{ border: 2px solid {text}; padding: 5px 11px; }}
            QPushButton:disabled {{ color: {disabled}; }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {base}; color: {text};
                border: 1px solid {border}; border-radius: 3px; padding: 4px; min-height: 22px; }}
            QComboBox QAbstractItemView {{ background: {base}; color: {text};
                selection-background-color: {highlight}; selection-color: {text}; }}
            QTableView {{ background: {base}; alternate-background-color: {alternate};
                          color: {text}; gridline-color: {border};
                          selection-background-color: {highlight}; selection-color: {text}; }}
            QHeaderView::section {{ background: {button}; color: {text}; padding: 7px 5px;
                                   border: 0; border-right: 1px solid {border}; }}
            QTabBar::tab {{ padding: 8px 12px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {base}; border-bottom: 2px solid {text}; }}
            QTextBrowser {{ background: {base}; color: {text}; border: 1px solid {border}; }}
            QToolTip {{ background: {base}; color: {text}; border: 1px solid {border}; }}
        """)
        for canvas in self.window.findChildren(FigureCanvasQTAgg):
            style_figure(canvas, dark)
            canvas.draw_idle()


class AdaptiveCanvas(FigureCanvasQTAgg):
    """Aplica el contraste también a gráficas creadas o recalculadas después del tema."""

    def __init__(self, figure=None):
        super().__init__(figure)
        self._preferred_size = QSize(*self.get_width_height())

    def sizeHint(self):
        # Matplotlib usa el tamaño actual de la figura como tamaño recomendado.
        # En pestañas dentro de un área desplazable eso realimenta el diseño:
        # cada ajuste del lienzo puede solicitar otro ajuste de sus contenedores.
        # Conserva la preferencia inicial; el lienzo sigue adaptándose al espacio.
        return QSize(self._preferred_size)

    def draw(self, *args, **kwargs):
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        style_figure(self, dark)
        return super().draw(*args, **kwargs)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.PaletteChange:
            self.draw_idle()
        super().changeEvent(event)
