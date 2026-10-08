"""Two-step CSV/XLSX import: preview → column mapping."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from doex.core import io as io_mod
from doex.core.schema import ColumnMapping


ROLE_CHOICES = [
    "ignore",
    "factor",
    "response",
    "sample_id",
]


class ImportWizard(QDialog):
    def __init__(self, path: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import table")
        self.resize(720, 480)
        self.path = Path(path)
        self.df = io_mod.read_table(self.path)
        self.mapping: ColumnMapping | None = None
        self.guess = io_mod.guess_mapping(self.df)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"File: {self.path.name}  ·  {len(self.df)} rows × {len(self.df.columns)} cols"))

        # Preview
        preview = QTableWidget()
        preview.setEditTriggers(QTableWidget.NoEditTriggers)
        n_show = min(8, len(self.df))
        cols = list(self.df.columns)
        preview.setColumnCount(len(cols))
        preview.setHorizontalHeaderLabels([str(c) for c in cols])
        preview.setRowCount(n_show)
        for r in range(n_show):
            for c, col in enumerate(cols):
                val = self.df.iloc[r][col]
                preview.setItem(r, c, QTableWidgetItem("" if pd.isna(val) else str(val)))
        preview.resizeColumnsToContents()
        root.addWidget(QLabel("Preview"))
        root.addWidget(preview, stretch=1)

        # Mapping row
        root.addWidget(QLabel("Column mapping"))
        map_row = QHBoxLayout()
        self.role_combos: dict[str, QComboBox] = {}
        for col in cols:
            box = QVBoxLayout()
            box.addWidget(QLabel(str(col)))
            combo = QComboBox()
            combo.addItems(ROLE_CHOICES)
            # apply guess
            role = "ignore"
            if self.guess.sample_id == col:
                role = "sample_id"
            elif col in self.guess.factors.values():
                role = "factor"
            elif col in self.guess.responses.values():
                role = "response"
            combo.setCurrentText(role)
            self.role_combos[str(col)] = combo
            box.addWidget(combo)
            map_row.addLayout(box)
        wrap = QWidget()
        wrap.setLayout(map_row)
        root.addWidget(wrap)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self) -> None:
        factors: dict[str, str] = {}
        responses: dict[str, str] = {}
        sample_id = None
        ignore: list[str] = []
        for col, combo in self.role_combos.items():
            role = combo.currentText()
            if role == "factor":
                factors[col] = col
            elif role == "response":
                responses[col] = col
            elif role == "sample_id":
                sample_id = col
            else:
                ignore.append(col)
        if not factors:
            self.mapping = None
            return
        self.mapping = ColumnMapping(
            factors=factors,
            responses=responses,
            sample_id=sample_id,
            ignore=ignore,
        )
        self.accept()
