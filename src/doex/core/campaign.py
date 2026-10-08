"""Campaign — first-class owner of schema, runs, settings, history."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from doex.core import io as io_mod
from doex.core.schema import (
    CampaignSchema,
    ColumnMapping,
    Factor,
    Response,
    RunStatus,
    SourceTag,
    SuggestMode,
    SuggestSettings,
)
from doex.core.suggest import predict_grid, suggest_batch
from doex.core.table import (
    align_to_schema,
    count_by_status,
    empty_runs,
    ensure_meta_columns,
    next_run_id,
    row_from_values,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Campaign:
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    schema: CampaignSchema = field(default_factory=CampaignSchema)
    runs: pd.DataFrame = field(default_factory=pd.DataFrame)
    settings: SuggestSettings = field(default_factory=SuggestSettings)
    history: list[dict[str, Any]] = field(default_factory=list)
    path: Path | None = None

    # ------------------------------------------------------------------ ctors
    @classmethod
    def create(cls, name: str) -> Campaign:
        c = cls(name=name)
        c.runs = empty_runs(c.schema)
        c._log("create", {"name": name})
        return c

    @classmethod
    def load(cls, path: str | Path) -> Campaign:
        path = Path(path)
        meta, runs = io_mod.load_campaign_dir(path)
        schema = CampaignSchema.from_dict(meta.get("schema", {}))
        settings = SuggestSettings.from_dict(meta.get("settings", {}))
        c = cls(
            name=meta.get("name", path.name),
            id=meta.get("id", str(uuid.uuid4())),
            created_at=meta.get("created_at", _utcnow()),
            updated_at=meta.get("updated_at", _utcnow()),
            schema=schema,
            runs=align_to_schema(ensure_meta_columns(runs), schema) if len(runs) else empty_runs(schema),
            settings=settings,
            history=list(meta.get("history", [])),
            path=path,
        )
        return c

    # ------------------------------------------------------------------ mutate
    def touch(self) -> None:
        self.updated_at = _utcnow()

    def _log(self, event: str, detail: dict[str, Any] | None = None) -> None:
        self.history.append({"at": _utcnow(), "event": event, "detail": detail or {}})
        self.touch()

    def set_factor(self, factor: Factor, *, replace_name: str | None = None) -> None:
        factor.validate()
        names = self.schema.factor_names()
        if replace_name and replace_name in names:
            idx = names.index(replace_name)
            old = self.schema.factors[idx]
            self.schema.factors[idx] = factor
            if old.name != factor.name and old.name in self.runs.columns:
                self.runs = self.runs.rename(columns={old.name: factor.name})
            self._log("set_factor", {"name": factor.name, "replaced": replace_name})
        elif factor.name in names:
            idx = names.index(factor.name)
            self.schema.factors[idx] = factor
            self._log("set_factor", {"name": factor.name})
        else:
            self.schema.factors.append(factor)
            if factor.name not in self.runs.columns:
                self.runs[factor.name] = pd.NA
            self._log("add_factor", {"name": factor.name})
        self.schema.validate()
        self.runs = align_to_schema(self.runs, self.schema)

    def remove_factor(self, name: str) -> None:
        self.schema.factors = [f for f in self.schema.factors if f.name != name]
        if name in self.runs.columns:
            self.runs = self.runs.drop(columns=[name])
        self._log("remove_factor", {"name": name})
        self.runs = align_to_schema(self.runs, self.schema)

    def set_response(self, response: Response, *, replace_name: str | None = None) -> None:
        response.validate()
        names = self.schema.response_names()
        if replace_name and replace_name in names:
            idx = names.index(replace_name)
            old = self.schema.responses[idx]
            self.schema.responses[idx] = response
            if old.name != response.name and old.name in self.runs.columns:
                self.runs = self.runs.rename(columns={old.name: response.name})
            self._log("set_response", {"name": response.name, "replaced": replace_name})
        elif response.name in names:
            idx = names.index(response.name)
            self.schema.responses[idx] = response
            self._log("set_response", {"name": response.name})
        else:
            self.schema.responses.append(response)
            if response.name not in self.runs.columns:
                self.runs[response.name] = pd.NA
            self._log("add_response", {"name": response.name})
        if self.settings.active_response is None:
            self.settings.active_response = response.name
        self.schema.validate()
        self.runs = align_to_schema(self.runs, self.schema)

    def remove_response(self, name: str) -> None:
        self.schema.responses = [r for r in self.schema.responses if r.name != name]
        if name in self.runs.columns:
            self.runs = self.runs.drop(columns=[name])
        if self.settings.active_response == name:
            self.settings.active_response = (
                self.schema.responses[0].name if self.schema.responses else None
            )
        self._log("remove_response", {"name": name})
        self.runs = align_to_schema(self.runs, self.schema)

    def update_settings(self, settings: SuggestSettings | None = None, **kwargs: Any) -> None:
        if settings is not None:
            self.settings = settings
        for k, v in kwargs.items():
            if k == "mode" and isinstance(v, str):
                self.settings.apply_mode(SuggestMode(v))
            elif k == "mode" and isinstance(v, SuggestMode):
                self.settings.apply_mode(v)
            elif hasattr(self.settings, k):
                setattr(self.settings, k, v)
        self._log("update_settings", self.settings.to_dict())

    # ------------------------------------------------------------------ import
    def import_table(self, df: pd.DataFrame, mapping: ColumnMapping) -> None:
        if not self.schema.factors and not self.schema.responses:
            self.schema = io_mod.infer_schema_from_df(df, mapping)
        mapped = io_mod.apply_mapping(df, mapping, self.schema)
        if len(self.runs) == 0:
            self.runs = mapped
        else:
            self.runs = pd.concat([self.runs, mapped], ignore_index=True)
            self.runs = align_to_schema(self.runs, self.schema)
        if self.settings.active_response is None and self.schema.responses:
            self.settings.active_response = self.schema.responses[0].name
        self._log("import_table", {"rows": len(mapped)})

    @classmethod
    def from_table(
        cls,
        name: str,
        df: pd.DataFrame,
        mapping: ColumnMapping | None = None,
    ) -> Campaign:
        mapping = mapping or io_mod.guess_mapping(df)
        c = cls.create(name)
        c.import_table(df, mapping)
        return c

    # ------------------------------------------------------------------ suggest cycle
    def suggest(self, k: int | None = None) -> list[dict[str, Any]]:
        if not self.schema.factors:
            raise ValueError("Define at least one factor before suggesting runs")
        batch = suggest_batch(self.runs, self.schema, self.settings, k=k)
        added: list[dict[str, Any]] = []
        for vals, reason in batch:
            rid = next_run_id(self.runs)
            row = row_from_values(
                self.schema,
                vals,
                run_id=rid,
                status=RunStatus.PROPOSED,
                reason=reason,
                source_tag=SourceTag.PROPOSED,
            )
            self.runs = pd.concat([self.runs, pd.DataFrame([row])], ignore_index=True)
            self.runs = align_to_schema(self.runs, self.schema)
            added.append(row)
        self._log(
            "suggest",
            {
                "k": len(added),
                "algorithm": self.settings.algorithm.value,
                "mode": self.settings.mode.value,
                "run_ids": [r["run_id"] for r in added],
            },
        )
        return added

    def accept_proposal(self, run_id: str) -> None:
        self._set_status(run_id, RunStatus.QUEUED)
        self._log("accept_proposal", {"run_id": run_id})

    def reject_proposal(self, run_id: str) -> None:
        self._set_status(run_id, RunStatus.REJECTED)
        self._log("reject_proposal", {"run_id": run_id})

    def record_results(self, run_id: str, values: dict[str, Any]) -> None:
        idx = self._index_of(run_id)
        for key, val in values.items():
            if key in self.runs.columns:
                self.runs.at[idx, key] = val
        self.runs.at[idx, "status"] = RunStatus.DONE.value
        self.runs.at[idx, "source_tag"] = SourceTag.EXPERIMENT.value
        self._log("record_results", {"run_id": run_id, "values": values})

    def _index_of(self, run_id: str) -> int:
        hits = self.runs.index[self.runs["run_id"].astype(str) == str(run_id)].tolist()
        if not hits:
            raise KeyError(f"Unknown run_id: {run_id}")
        return int(hits[0])

    def _set_status(self, run_id: str, status: RunStatus) -> None:
        idx = self._index_of(run_id)
        self.runs.at[idx, "status"] = status.value
        self.touch()

    # ------------------------------------------------------------------ viz
    def slice_2d(
        self,
        x: str,
        y: str,
        response_or: str = "response",
        frozen: dict[str, Any] | None = None,
        resolution: int = 40,
    ) -> dict[str, Any]:
        what = "acquisition" if response_or == "acquisition" else "response"
        return predict_grid(
            self.runs,
            self.schema,
            self.settings,
            x_name=x,
            y_name=y,
            frozen=frozen,
            resolution=resolution,
            what=what,
        )

    # ------------------------------------------------------------------ persist
    def to_meta(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema": self.schema.to_dict(),
            "settings": self.settings.to_dict(),
            "history": self.history,
        }

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path is not None else self.path
        if path is None:
            raise ValueError("No path given for save")
        self.touch()
        saved = io_mod.save_campaign_dir(path, self.to_meta(), self.runs)
        self.path = saved
        self._log("save", {"path": str(saved)})
        return saved

    def export(self, path: str | Path, kind: str = "campaign") -> Path:
        path = Path(path)
        if kind == "runs":
            io_mod.write_runs_csv(self.runs, path)
            return path
        if kind == "schema":
            io_mod.export_schema_json(self.schema, path)
            return path
        # full campaign directory
        return self.save(path)

    def status_counts(self) -> dict[str, int]:
        return count_by_status(self.runs)
