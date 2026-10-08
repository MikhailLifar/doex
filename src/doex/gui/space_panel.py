"""Space editor — factors and responses (basics + advanced types)."""

from __future__ import annotations

from typing import Callable

from PyQt5.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from doex.core.campaign import Campaign
from doex.core.schema import Factor, FactorType, Response, ResponseGoal
from doex.gui.widgets.dialogs import show_error


class SpacePanel(QWidget):
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

        # Factors
        fg = QGroupBox("Factors")
        fl = QVBoxLayout(fg)
        self.factor_table = QTableWidget(0, 5)
        self.factor_table.setHorizontalHeaderLabels(["Name", "Type", "Low", "High", "Unit"])
        fl.addWidget(self.factor_table)
        fbtns = QHBoxLayout()
        self.btn_add_f = QPushButton("Add factor")
        self.btn_del_f = QPushButton("Remove selected")
        self.btn_apply_f = QPushButton("Apply bounds")
        self.btn_add_f.clicked.connect(self._add_factor)
        self.btn_del_f.clicked.connect(self._remove_factor)
        self.btn_apply_f.clicked.connect(self._apply_factors)
        fbtns.addWidget(self.btn_add_f)
        fbtns.addWidget(self.btn_del_f)
        fbtns.addWidget(self.btn_apply_f)
        fbtns.addStretch(1)
        fl.addLayout(fbtns)
        root.addWidget(fg)

        # Responses
        rg = QGroupBox("Responses")
        rl = QVBoxLayout(rg)
        self.resp_table = QTableWidget(0, 3)
        self.resp_table.setHorizontalHeaderLabels(["Name", "Goal", "Unit"])
        rl.addWidget(self.resp_table)
        rbtns = QHBoxLayout()
        self.btn_add_r = QPushButton("Add response")
        self.btn_del_r = QPushButton("Remove selected")
        self.btn_apply_r = QPushButton("Apply")
        self.btn_add_r.clicked.connect(self._add_response)
        self.btn_del_r.clicked.connect(self._remove_response)
        self.btn_apply_r.clicked.connect(self._apply_responses)
        rbtns.addWidget(self.btn_add_r)
        rbtns.addWidget(self.btn_del_r)
        rbtns.addWidget(self.btn_apply_r)
        rbtns.addStretch(1)
        rl.addLayout(rbtns)
        root.addWidget(rg)

        tip = QLabel("Changing bounds applies to the next Suggest without restarting.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #555;")
        root.addWidget(tip)
        root.addStretch(1)
        self.reload()

    def set_campaign(self, campaign: Campaign) -> None:
        self.campaign = campaign
        self.reload()

    def reload(self) -> None:
        factors = self.campaign.schema.factors
        self.factor_table.setRowCount(len(factors))
        for i, f in enumerate(factors):
            self.factor_table.setItem(i, 0, QTableWidgetItem(f.name))
            type_combo = QComboBox()
            for t in FactorType:
                type_combo.addItem(t.value)
            type_combo.setCurrentText(f.type.value)
            self.factor_table.setCellWidget(i, 1, type_combo)
            lo = "" if f.bounds is None else str(f.bounds[0])
            hi = "" if f.bounds is None else str(f.bounds[1])
            self.factor_table.setItem(i, 2, QTableWidgetItem(lo))
            self.factor_table.setItem(i, 3, QTableWidgetItem(hi))
            self.factor_table.setItem(i, 4, QTableWidgetItem(f.unit or ""))

        resps = self.campaign.schema.responses
        self.resp_table.setRowCount(len(resps))
        for i, r in enumerate(resps):
            self.resp_table.setItem(i, 0, QTableWidgetItem(r.name))
            goal = QComboBox()
            for g in ResponseGoal:
                goal.addItem(g.value)
            goal.setCurrentText(r.goal.value)
            self.resp_table.setCellWidget(i, 1, goal)
            self.resp_table.setItem(i, 2, QTableWidgetItem(r.unit or ""))

        self.factor_table.resizeColumnsToContents()
        self.resp_table.resizeColumnsToContents()

    def _add_factor(self) -> None:
        name, ok = QInputDialog.getText(self, "Add factor", "Name:")
        if not ok or not name.strip():
            return
        try:
            self.campaign.set_factor(
                Factor(name=name.strip(), type=FactorType.CONTINUOUS, bounds=(0.0, 1.0))
            )
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Factor", str(exc), exc)
            return
        self.reload()
        if self.on_changed:
            self.on_changed()

    def _remove_factor(self) -> None:
        rows = sorted({i.row() for i in self.factor_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        reply = QMessageBox.question(
            self,
            "Remove factor",
            "Remove selected factor(s) and their columns from runs?",
        )
        if reply != QMessageBox.Yes:
            return
        for r in rows:
            item = self.factor_table.item(r, 0)
            if item:
                self.campaign.remove_factor(item.text())
        self.reload()
        if self.on_changed:
            self.on_changed()

    def _apply_factors(self) -> None:
        try:
            for i in range(self.factor_table.rowCount()):
                name_item = self.factor_table.item(i, 0)
                if not name_item:
                    continue
                name = name_item.text().strip()
                type_w = self.factor_table.cellWidget(i, 1)
                assert isinstance(type_w, QComboBox)
                ftype = FactorType(type_w.currentText())
                lo_s = (self.factor_table.item(i, 2).text() if self.factor_table.item(i, 2) else "").strip()
                hi_s = (self.factor_table.item(i, 3).text() if self.factor_table.item(i, 3) else "").strip()
                unit = (self.factor_table.item(i, 4).text() if self.factor_table.item(i, 4) else "") or None
                old = None
                try:
                    old = self.campaign.schema.get_factor(name)
                except KeyError:
                    # renamed? use row order
                    if i < len(self.campaign.schema.factors):
                        old = self.campaign.schema.factors[i]
                bounds = None
                levels = old.levels if old else None
                fixed_value = old.fixed_value if old else None
                if ftype in (FactorType.CONTINUOUS, FactorType.INTEGER, FactorType.FIXED):
                    if lo_s and hi_s:
                        bounds = (float(lo_s), float(hi_s))
                    elif old and old.bounds:
                        bounds = old.bounds
                    else:
                        bounds = (0.0, 1.0)
                factor = Factor(
                    name=name,
                    type=ftype,
                    bounds=bounds,
                    levels=levels,
                    unit=unit,
                    fixed_value=fixed_value,
                )
                replace = old.name if old and old.name != name else None
                if replace:
                    self.campaign.set_factor(factor, replace_name=replace)
                else:
                    self.campaign.set_factor(factor)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Apply factors", str(exc), exc)
            return
        self.reload()
        if self.on_changed:
            self.on_changed()

    def _add_response(self) -> None:
        name, ok = QInputDialog.getText(self, "Add response", "Name:")
        if not ok or not name.strip():
            return
        try:
            self.campaign.set_response(Response(name=name.strip(), goal=ResponseGoal.MAXIMIZE))
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Response", str(exc), exc)
            return
        self.reload()
        if self.on_changed:
            self.on_changed()

    def _remove_response(self) -> None:
        rows = sorted({i.row() for i in self.resp_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        reply = QMessageBox.question(self, "Remove response", "Remove selected response(s)?")
        if reply != QMessageBox.Yes:
            return
        for r in rows:
            item = self.resp_table.item(r, 0)
            if item:
                self.campaign.remove_response(item.text())
        self.reload()
        if self.on_changed:
            self.on_changed()

    def _apply_responses(self) -> None:
        try:
            for i in range(self.resp_table.rowCount()):
                name_item = self.resp_table.item(i, 0)
                if not name_item:
                    continue
                name = name_item.text().strip()
                goal_w = self.resp_table.cellWidget(i, 1)
                assert isinstance(goal_w, QComboBox)
                unit = (self.resp_table.item(i, 2).text() if self.resp_table.item(i, 2) else "") or None
                old = None
                try:
                    old = self.campaign.schema.get_response(name)
                except KeyError:
                    if i < len(self.campaign.schema.responses):
                        old = self.campaign.schema.responses[i]
                resp = Response(name=name, goal=ResponseGoal(goal_w.currentText()), unit=unit)
                if old and old.name != name:
                    self.campaign.set_response(resp, replace_name=old.name)
                else:
                    self.campaign.set_response(resp)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Apply responses", str(exc), exc)
            return
        self.reload()
        if self.on_changed:
            self.on_changed()
