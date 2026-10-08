"""Runs table — primary working object."""

from __future__ import annotations

from typing import Callable

import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from doex.core.campaign import Campaign
from doex.core.schema import RunStatus


class RunsPanel(QWidget):
    def __init__(
        self,
        campaign: Campaign,
        on_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.campaign = campaign
        self.on_changed = on_changed
        self._suppress = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        self.hint = QLabel("Edit cells directly. Proposed rows: fill responses then Mark done.")
        self.hint.setWordWrap(True)
        bar.addWidget(self.hint, stretch=1)
        self.btn_done = QPushButton("Mark selected done")
        self.btn_reject = QPushButton("Reject selected")
        self.btn_done.clicked.connect(self._mark_done)
        self.btn_reject.clicked.connect(self._reject)
        bar.addWidget(self.btn_done)
        bar.addWidget(self.btn_reject)
        layout.addLayout(bar)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)
        self.reload()

    def set_campaign(self, campaign: Campaign) -> None:
        self.campaign = campaign
        self.reload()

    def reload(self) -> None:
        self._suppress = True
        df = self.campaign.runs
        cols = list(df.columns) if df is not None else []
        self.table.clear()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(0 if df is None else len(df))
        if df is not None and len(df):
            for r in range(len(df)):
                for c, col in enumerate(cols):
                    val = df.iloc[r][col]
                    text = "" if pd.isna(val) else str(val)
                    item = QTableWidgetItem(text)
                    if col == "run_id":
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        self._suppress = False

    def _col_index(self, name: str) -> int:
        for i in range(self.table.columnCount()):
            if self.table.horizontalHeaderItem(i).text() == name:
                return i
        return -1

    def _selected_run_ids(self) -> list[str]:
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        rid_col = self._col_index("run_id")
        out = []
        for r in sorted(rows):
            item = self.table.item(r, rid_col)
            if item:
                out.append(item.text())
        return out

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._suppress:
            return
        col_name = self.table.horizontalHeaderItem(item.column()).text()
        rid_col = self._col_index("run_id")
        rid_item = self.table.item(item.row(), rid_col)
        if rid_item is None:
            return
        run_id = rid_item.text()
        try:
            idx = self.campaign._index_of(run_id)
        except KeyError:
            return
        raw = item.text().strip()
        if raw == "":
            self.campaign.runs.at[idx, col_name] = pd.NA
        else:
            # try numeric for factor/response columns
            if col_name in self.campaign.schema.factor_names() + self.campaign.schema.response_names():
                try:
                    if "." in raw or "e" in raw.lower():
                        self.campaign.runs.at[idx, col_name] = float(raw)
                    else:
                        # keep as float for continuous consistency
                        self.campaign.runs.at[idx, col_name] = float(raw)
                except ValueError:
                    self.campaign.runs.at[idx, col_name] = raw
            else:
                self.campaign.runs.at[idx, col_name] = raw
        self.campaign.touch()
        if self.on_changed:
            self.on_changed()

    def _mark_done(self) -> None:
        rids = self._selected_run_ids()
        if not rids:
            QMessageBox.information(self, "Runs", "Select one or more rows first.")
            return
        for rid in rids:
            idx = self.campaign._index_of(rid)
            self.campaign.runs.at[idx, "status"] = RunStatus.DONE.value
        self.campaign.touch()
        self.reload()
        if self.on_changed:
            self.on_changed()

    def _reject(self) -> None:
        rids = self._selected_run_ids()
        if not rids:
            return
        for rid in rids:
            try:
                self.campaign.reject_proposal(rid)
            except KeyError:
                pass
        self.reload()
        if self.on_changed:
            self.on_changed()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Delete:
            self._reject()
            return
        super().keyPressEvent(event)
