"""Main window: home + campaign workspace (basics | tabs | advanced)."""

from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from doex import __version__
from doex.core.campaign import Campaign
from doex.core.schema import Factor, FactorType, Response, ResponseGoal
from doex.gui.import_wizard import ImportWizard
from doex.gui.next_panel import NextPanel
from doex.gui.runs_panel import RunsPanel
from doex.gui.space_panel import SpacePanel
from doex.gui.viz_panel import VizPanel
from doex.gui.widgets.dialogs import show_error

RECENT_PATH = Path.home() / ".doex_recent.json"
MAX_RECENT = 12


def _load_recent() -> list[str]:
    if not RECENT_PATH.exists():
        return []
    try:
        data = json.loads(RECENT_PATH.read_text(encoding="utf-8"))
        return [p for p in data if isinstance(p, str)]
    except Exception:  # noqa: BLE001
        return []


def _save_recent(paths: list[str]) -> None:
    RECENT_PATH.write_text(json.dumps(paths[:MAX_RECENT], indent=2), encoding="utf-8")


def _remember(path: str | Path) -> None:
    path = str(Path(path).resolve())
    items = [path] + [p for p in _load_recent() if p != path]
    _save_recent(items)


class HomePage(QWidget):
    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self.owner = owner
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        brand = QLabel("doex")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet("font-size: 42px; font-weight: 600; letter-spacing: 0.04em; color: #1a3a3a;")
        root.addWidget(brand)

        sub = QLabel("Adaptive design of experiments for lab campaigns")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 14px; color: #445;")
        root.addWidget(sub)
        root.addSpacing(24)

        btn_new = QPushButton("New campaign")
        btn_open = QPushButton("Continue from file…")
        btn_import = QPushButton("Import table…")
        for b in (btn_new, btn_open, btn_import):
            b.setMinimumWidth(260)
            b.setMinimumHeight(36)
            root.addWidget(b, alignment=Qt.AlignCenter)
        btn_new.clicked.connect(owner.new_campaign)
        btn_open.clicked.connect(owner.open_campaign)
        btn_import.clicked.connect(owner.import_table)

        root.addSpacing(20)
        root.addWidget(QLabel("Recent"), alignment=Qt.AlignCenter)
        self.recent = QListWidget()
        self.recent.setMaximumWidth(420)
        self.recent.setMaximumHeight(160)
        self.recent.itemDoubleClicked.connect(self._open_recent)
        root.addWidget(self.recent, alignment=Qt.AlignCenter)
        self.refresh_recent()

    def refresh_recent(self) -> None:
        self.recent.clear()
        for p in _load_recent():
            self.recent.addItem(p)

    def _open_recent(self) -> None:
        item = self.recent.currentItem()
        if item:
            self.owner.open_campaign_path(item.text())


class BasicsSidebar(QWidget):
    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self.owner = owner
        self.setFixedWidth(220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.name_label = QLabel("Campaign")
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #1a3a3a;")
        layout.addWidget(self.name_label)

        self.counts = QLabel("done 0 · proposed 0")
        self.counts.setStyleSheet("color: #555;")
        layout.addWidget(self.counts)

        layout.addWidget(QLabel("Batch size K"))
        self.batch = QSpinBox()
        self.batch.setRange(1, 50)
        self.batch.setValue(3)
        self.batch.valueChanged.connect(self._sync_batch)
        layout.addWidget(self.batch)

        layout.addWidget(QLabel("Optimize response"))
        self.response = QComboBox()
        self.response.currentIndexChanged.connect(self._sync_response)
        layout.addWidget(self.response)

        self.btn_suggest = QPushButton("Suggest next")
        self.btn_suggest.setMinimumHeight(40)
        self.btn_suggest.setStyleSheet(
            "QPushButton { background: #2a6f6f; color: white; font-weight: 600; border: none; }"
            "QPushButton:hover { background: #1f5757; }"
        )
        self.btn_suggest.clicked.connect(owner.suggest_next)
        layout.addWidget(self.btn_suggest)

        layout.addSpacing(8)
        self.btn_import = QPushButton("Import…")
        self.btn_export = QPushButton("Export…")
        self.btn_save = QPushButton("Save")
        self.btn_import.clicked.connect(owner.import_table)
        self.btn_export.clicked.connect(owner.export_campaign)
        self.btn_save.clicked.connect(owner.save_campaign)
        layout.addWidget(self.btn_import)
        layout.addWidget(self.btn_export)
        layout.addWidget(self.btn_save)
        layout.addStretch(1)

        home = QPushButton("← Home")
        home.clicked.connect(owner.show_home)
        layout.addWidget(home)

    def refresh(self) -> None:
        c = self.owner.campaign
        if c is None:
            return
        self.name_label.setText(c.name)
        counts = c.status_counts()
        self.counts.setText(
            f"done {counts.get('done', 0)} · proposed {counts.get('proposed', 0)}"
        )
        self.batch.blockSignals(True)
        self.batch.setValue(c.settings.batch_size)
        self.batch.blockSignals(False)

        self.response.blockSignals(True)
        self.response.clear()
        names = c.schema.response_names()
        self.response.addItems(names)
        if c.settings.active_response and c.settings.active_response in names:
            self.response.setCurrentText(c.settings.active_response)
        self.response.blockSignals(False)

    def _sync_batch(self, value: int) -> None:
        if self.owner.campaign:
            self.owner.campaign.update_settings(batch_size=int(value))

    def _sync_response(self) -> None:
        if self.owner.campaign and self.response.currentText():
            self.owner.campaign.update_settings(active_response=self.response.currentText())


class CampaignPage(QWidget):
    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self.owner = owner
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.basics = BasicsSidebar(owner)
        root.addWidget(self.basics)

        splitter = QSplitter(Qt.Horizontal)
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(4, 4, 4, 4)
        self.tabs = QTabWidget()
        # panels created when campaign is set
        self.runs_panel: RunsPanel | None = None
        self.space_panel: SpacePanel | None = None
        self.viz_panel: VizPanel | None = None
        self.next_panel: NextPanel | None = None
        cl.addWidget(self.tabs)
        splitter.addWidget(center)

        # Advanced drawer (collapsed by default)
        adv_wrap = QFrame()
        adv_wrap.setFrameShape(QFrame.StyledPanel)
        adv_l = QVBoxLayout(adv_wrap)
        adv_l.setContentsMargins(6, 6, 6, 6)
        self.adv_toggle = QToolButton()
        self.adv_toggle.setText("Advanced ▸")
        self.adv_toggle.setCheckable(True)
        self.adv_toggle.setChecked(False)
        self.adv_toggle.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.adv_toggle.setMinimumHeight(28)
        self.adv_toggle.toggled.connect(self._toggle_advanced)
        adv_l.addWidget(self.adv_toggle)
        self.adv_body = QWidget()
        self.adv_body_layout = QVBoxLayout(self.adv_body)
        self.adv_body_layout.setContentsMargins(0, 0, 0, 0)
        self.adv_body.setVisible(False)
        adv_l.addWidget(self.adv_body)
        adv_wrap.setMinimumWidth(120)
        splitter.addWidget(adv_wrap)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 160])
        self._adv_wrap = adv_wrap
        self._splitter = splitter

        root.addWidget(splitter, stretch=1)

    def _toggle_advanced(self, on: bool) -> None:
        self.adv_body.setVisible(on)
        self.adv_toggle.setText("Advanced ▾" if on else "Advanced ▸")

    def bind_campaign(self, campaign: Campaign) -> None:
        self.tabs.clear()
        # clear advanced
        while self.adv_body_layout.count():
            item = self.adv_body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.runs_panel = RunsPanel(campaign, on_changed=self.owner.on_campaign_changed)
        self.space_panel = SpacePanel(campaign, on_changed=self.owner.on_campaign_changed)
        self.viz_panel = VizPanel(campaign, on_changed=self.owner.on_campaign_changed)
        self.next_panel = NextPanel(campaign, on_changed=self.owner.on_campaign_changed)

        self.tabs.addTab(self.runs_panel, "Runs")
        self.tabs.addTab(self.space_panel, "Space")
        self.tabs.addTab(self.viz_panel, "Maps")
        self.adv_body_layout.addWidget(self.next_panel)
        self.basics.refresh()

    def refresh(self) -> None:
        self.basics.refresh()
        if self.runs_panel:
            self.runs_panel.reload()
        if self.space_panel:
            self.space_panel.reload()
        if self.viz_panel:
            self.viz_panel.refresh()
        if self.next_panel:
            self.next_panel.reload()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"doex {__version__}")
        self.resize(1100, 700)
        self.campaign: Campaign | None = None

        self.stack = QStackedWidget()
        self.home = HomePage(self)
        self.campaign_page = CampaignPage(self)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.campaign_page)
        self.setCentralWidget(self.stack)

        self._build_menu()
        self._apply_palette()
        self.show_home()

    def _apply_palette(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f3f1ec;
                font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
                font-size: 13px;
                color: #1c1c1c;
            }
            QTabWidget::pane { border: 1px solid #cfcac0; background: #faf9f6; }
            QTabBar::tab {
                background: #e8e4db; padding: 8px 14px; margin-right: 2px;
                border: 1px solid #cfcac0; border-bottom: none;
            }
            QTabBar::tab:selected { background: #faf9f6; font-weight: 600; }
            QTableWidget {
                background: #faf9f6; gridline-color: #ddd8ce;
                alternate-background-color: #f0ece4;
            }
            QPushButton {
                background: #e8e4db; border: 1px solid #bdb7aa;
                padding: 6px 10px;
            }
            QPushButton:hover { background: #ddd7cb; }
            QListWidget { background: #faf9f6; border: 1px solid #cfcac0; }
            QFrame { background: #ebe7df; }
            """
        )

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        act_new = QAction("New campaign", self)
        act_new.setShortcut(QKeySequence.New)
        act_new.triggered.connect(self.new_campaign)
        act_open = QAction("Open…", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self.open_campaign)
        act_save = QAction("Save", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self.save_campaign)
        act_import = QAction("Import table…", self)
        act_import.triggered.connect(self.import_table)
        act_export = QAction("Export…", self)
        act_export.triggered.connect(self.export_campaign)
        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        for a in (act_new, act_open, act_save, act_import, act_export, act_quit):
            file_menu.addAction(a)

        run_menu = self.menuBar().addMenu("&Run")
        act_suggest = QAction("Suggest next", self)
        act_suggest.setShortcut(QKeySequence("Ctrl+Return"))
        act_suggest.triggered.connect(self.suggest_next)
        run_menu.addAction(act_suggest)

        view_menu = self.menuBar().addMenu("&View")
        for i, name in enumerate(("Runs", "Space", "Maps"), start=1):
            act = QAction(f"{name} tab", self)
            act.setShortcut(QKeySequence(f"Ctrl+{i}"))
            act.triggered.connect(lambda _checked=False, idx=i - 1: self._focus_tab(idx))
            view_menu.addAction(act)

    def _focus_tab(self, index: int) -> None:
        if self.stack.currentWidget() is self.campaign_page:
            self.campaign_page.tabs.setCurrentIndex(index)

    def show_home(self) -> None:
        self.home.refresh_recent()
        self.stack.setCurrentWidget(self.home)

    def _open_campaign_ui(self, campaign: Campaign) -> None:
        self.campaign = campaign
        self.campaign_page.bind_campaign(campaign)
        self.stack.setCurrentWidget(self.campaign_page)
        self.setWindowTitle(f"doex — {campaign.name}")

    def on_campaign_changed(self) -> None:
        if self.campaign is None:
            return
        self.campaign_page.basics.refresh()
        # light refresh of maps if visible
        if self.campaign_page.viz_panel and self.campaign_page.tabs.currentWidget() is self.campaign_page.viz_panel:
            self.campaign_page.viz_panel.refresh()

    # ----- actions
    def new_campaign(self) -> None:
        name, ok = QInputDialog.getText(self, "New campaign", "Campaign name:", text="Untitled")
        if not ok or not name.strip():
            return
        c = Campaign.create(name.strip())
        # seed with a minimal demo space so Suggest works immediately
        c.set_factor(Factor("x1", FactorType.CONTINUOUS, bounds=(0.0, 1.0)))
        c.set_factor(Factor("x2", FactorType.CONTINUOUS, bounds=(0.0, 1.0)))
        c.set_response(Response("y", ResponseGoal.MAXIMIZE))
        c.update_settings(active_response="y", batch_size=3)
        self._open_campaign_ui(c)

    def open_campaign(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open campaign folder (.doex dir)")
        if not path:
            return
        self.open_campaign_path(path)

    def open_campaign_path(self, path: str) -> None:
        try:
            c = Campaign.load(path)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Open failed", f"Could not open campaign:\n{exc}", exc)
            return
        _remember(path)
        self._open_campaign_ui(c)

    def save_campaign(self) -> None:
        if self.campaign is None:
            return
        path = self.campaign.path
        if path is None:
            path_str = QFileDialog.getExistingDirectory(self, "Save campaign as folder")
            if not path_str:
                # allow creating a new folder name via save dialog workaround
                path_str, _ = QFileDialog.getSaveFileName(
                    self, "Save campaign", f"{self.campaign.name}.doex", "doex campaign (*.doex)"
                )
                if not path_str:
                    return
            path = Path(path_str)
        try:
            saved = self.campaign.save(path)
            _remember(saved)
            self.statusBar().showMessage(f"Saved: {saved}", 5000)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Save failed", str(exc), exc)

    def import_table(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import table",
            str(Path.cwd() / "examples"),
            "Tables (*.csv *.xlsx *.xls);;CSV (*.csv);;All (*)",
        )
        if not path:
            return
        try:
            wiz = ImportWizard(path, self)
            if wiz.exec_() != wiz.Accepted or wiz.mapping is None:
                return
            if self.campaign is None:
                name = Path(path).stem
                self.campaign = Campaign.create(name)
                self._open_campaign_ui(self.campaign)
            assert self.campaign is not None
            # if empty schema, import builds it; if existing, mapping must match names
            self.campaign.import_table(wiz.df, wiz.mapping)
            self.campaign_page.bind_campaign(self.campaign)
            self.campaign_page.refresh()
            self.statusBar().showMessage(f"Imported {len(wiz.df)} rows", 5000)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Import failed", str(exc), exc)

    def export_campaign(self) -> None:
        if self.campaign is None:
            return
        path, selected = QFileDialog.getSaveFileName(
            self,
            "Export",
            f"{self.campaign.name}_runs.csv",
            "Runs CSV (*.csv);;Schema JSON (*.json);;Campaign folder (*.doex)",
        )
        if not path:
            return
        try:
            if selected.startswith("Schema") or path.endswith(".json"):
                self.campaign.export(path, kind="schema")
            elif selected.startswith("Campaign") or path.endswith(".doex"):
                self.campaign.export(path, kind="campaign")
                _remember(path)
            else:
                self.campaign.export(path, kind="runs")
            self.statusBar().showMessage(f"Exported: {path}", 5000)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Export failed", str(exc), exc)

    def suggest_next(self) -> None:
        if self.campaign is None:
            return
        try:
            batch = self.campaign.suggest()
            self.campaign_page.refresh()
            self.campaign_page.tabs.setCurrentIndex(0)
            self.statusBar().showMessage(f"Proposed {len(batch)} run(s)", 5000)
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Suggest failed", str(exc), exc)
