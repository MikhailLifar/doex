"""Advanced suggest settings (drawer content)."""

from __future__ import annotations

from typing import Callable

from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from doex.core.campaign import Campaign
from doex.core.schema import SuggestAlgorithm, SuggestMode


class NextPanel(QWidget):
    """Advanced: algorithm, seed, explore–exploit mix."""

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
        root.addWidget(QLabel("Advanced suggest settings"))
        form = QFormLayout()

        self.mode = QComboBox()
        # User-facing labels → SuggestMode
        self._mode_map = {
            "Fast (space-filling)": SuggestMode.FAST,
            "Balanced (trees)": SuggestMode.BALANCED,
            "Exploit": SuggestMode.EXPLOIT,
            "Explore space": SuggestMode.EXPLORE,
            "Ridge baseline": SuggestMode.RIDGE,
        }
        self.mode.addItems(list(self._mode_map.keys()))
        self.mode.currentIndexChanged.connect(self._apply_mode)
        form.addRow("Mode", self.mode)

        self.algorithm = QComboBox()
        for a in SuggestAlgorithm:
            self.algorithm.addItem(a.value)
        self.algorithm.currentIndexChanged.connect(self._apply_algo)
        form.addRow("Algorithm", self.algorithm)

        self.lam = QDoubleSpinBox()
        self.lam.setRange(0.0, 5.0)
        self.lam.setSingleStep(0.1)
        self.lam.valueChanged.connect(self._apply_numeric)
        form.addRow("Explore mix (λ)", self.lam)

        self.seed = QSpinBox()
        self.seed.setRange(0, 1_000_000)
        self.seed.valueChanged.connect(self._apply_numeric)
        form.addRow("Seed", self.seed)

        self.n_cand = QSpinBox()
        self.n_cand.setRange(32, 5000)
        self.n_cand.setSingleStep(32)
        self.n_cand.valueChanged.connect(self._apply_numeric)
        form.addRow("Candidates", self.n_cand)

        root.addLayout(form)
        tip = QLabel("Changes apply to the next Suggest — done runs are kept.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #555;")
        root.addWidget(tip)
        root.addStretch(1)
        self.reload()

    def set_campaign(self, campaign: Campaign) -> None:
        self.campaign = campaign
        self.reload()

    def reload(self) -> None:
        s = self.campaign.settings
        rev = {v: k for k, v in self._mode_map.items()}
        label = rev.get(s.mode, "Balanced (trees)")
        self.mode.blockSignals(True)
        self.algorithm.blockSignals(True)
        self.lam.blockSignals(True)
        self.seed.blockSignals(True)
        self.n_cand.blockSignals(True)
        self.mode.setCurrentText(label)
        self.algorithm.setCurrentText(s.algorithm.value)
        self.lam.setValue(s.explore_lambda)
        self.seed.setValue(s.seed)
        self.n_cand.setValue(s.n_candidates)
        self.mode.blockSignals(False)
        self.algorithm.blockSignals(False)
        self.lam.blockSignals(False)
        self.seed.blockSignals(False)
        self.n_cand.blockSignals(False)

    def _apply_mode(self) -> None:
        mode = self._mode_map[self.mode.currentText()]
        self.campaign.update_settings(mode=mode)
        self.reload()
        if self.on_changed:
            self.on_changed()

    def _apply_numeric(self) -> None:
        self.campaign.settings.explore_lambda = float(self.lam.value())
        self.campaign.settings.seed = int(self.seed.value())
        self.campaign.settings.n_candidates = int(self.n_cand.value())
        self.campaign.touch()
        if self.on_changed:
            self.on_changed()

    def _apply_algo(self) -> None:
        algo = SuggestAlgorithm(self.algorithm.currentText())
        self.campaign.update_settings(algorithm=algo)
        if self.on_changed:
            self.on_changed()
