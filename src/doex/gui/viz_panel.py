"""Maps tab — scatter and 2D model / acquisition slices."""

from __future__ import annotations

from typing import Callable

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from doex.core.campaign import Campaign
from doex.core.schema import FactorType
from doex.gui.widgets.dialogs import show_error
from doex.viz.slices2d import export_figure, plot_scatter, plot_slice


class VizPanel(QWidget):
    def __init__(
        self,
        campaign: Campaign,
        on_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.campaign = campaign
        self.on_changed = on_changed

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("X"))
        self.x_combo = QComboBox()
        controls.addWidget(self.x_combo)
        controls.addWidget(QLabel("Y"))
        self.y_combo = QComboBox()
        controls.addWidget(self.y_combo)
        controls.addWidget(QLabel("Color / slice"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["scatter: status", "scatter: response", "model slice", "acquisition"])
        controls.addWidget(self.mode_combo)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_export = QPushButton("Export PNG")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_export.clicked.connect(self._export_png)
        controls.addWidget(self.btn_refresh)
        controls.addWidget(self.btn_export)
        controls.addStretch(1)
        root.addLayout(controls)

        self.fig = Figure(figsize=(6, 4), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.ax = self.fig.add_subplot(111)
        root.addWidget(self.canvas)
        self._fill_axis_combos()
        self.refresh()
        # after initial paint — changing axes/mode redraws Maps
        self.x_combo.currentIndexChanged.connect(self.refresh)
        self.y_combo.currentIndexChanged.connect(self.refresh)
        self.mode_combo.currentIndexChanged.connect(self.refresh)

    def set_campaign(self, campaign: Campaign) -> None:
        self.campaign = campaign
        self._fill_axis_combos()
        self.refresh()

    def _numeric_factors(self) -> list[str]:
        return [
            f.name
            for f in self.campaign.schema.factors
            if f.type in (FactorType.CONTINUOUS, FactorType.INTEGER) and f.bounds
        ]

    def _fill_axis_combos(self) -> None:
        names = self._numeric_factors() or self.campaign.schema.factor_names()
        cur_x = self.x_combo.currentText()
        cur_y = self.y_combo.currentText()
        self.x_combo.blockSignals(True)
        self.y_combo.blockSignals(True)
        self.x_combo.clear()
        self.y_combo.clear()
        self.x_combo.addItems(names)
        self.y_combo.addItems(names)
        if cur_x in names:
            self.x_combo.setCurrentText(cur_x)
        if cur_y in names:
            self.y_combo.setCurrentText(cur_y)
        elif len(names) > 1:
            self.y_combo.setCurrentIndex(1)
        self.x_combo.blockSignals(False)
        self.y_combo.blockSignals(False)

    def refresh(self) -> None:
        self._fill_axis_combos()
        x = self.x_combo.currentText()
        y = self.y_combo.currentText()
        if not x or not y:
            self.ax.clear()
            self.ax.set_title("Add continuous factors to plot maps")
            self.canvas.draw_idle()
            return
        mode = self.mode_combo.currentText()
        try:
            if mode.startswith("scatter"):
                color_by = "status"
                if mode.endswith("response") and self.campaign.settings.active_response:
                    color_by = self.campaign.settings.active_response
                plot_scatter(
                    self.ax,
                    self.campaign.runs,
                    self.campaign.schema,
                    x_name=x,
                    y_name=y,
                    color_by=color_by,
                )
            else:
                what = "acquisition" if mode == "acquisition" else "response"
                grid = self.campaign.slice_2d(x, y, response_or=what)
                plot_slice(self.ax, grid, self.campaign.runs)
        except Exception as exc:  # noqa: BLE001
            self.ax.clear()
            self.ax.text(0.5, 0.5, str(exc), ha="center", va="center", transform=self.ax.transAxes)
        self.canvas.draw_idle()

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export figure", "map.png", "PNG (*.png)")
        if not path:
            return
        try:
            export_figure(self.fig, path)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Export", str(exc), exc)
