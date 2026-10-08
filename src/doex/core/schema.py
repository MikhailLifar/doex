"""Factor / response schema and suggest settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class FactorType(str, Enum):
    CONTINUOUS = "continuous"
    INTEGER = "integer"
    CATEGORICAL = "categorical"
    FIXED = "fixed"


class FactorRole(str, Enum):
    FREE = "free"
    SHARED_BATCH = "shared_batch"


class ResponseGoal(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    TARGET = "target"
    OBSERVE = "observe"


class RunStatus(str, Enum):
    DONE = "done"
    PROPOSED = "proposed"
    QUEUED = "queued"
    REJECTED = "rejected"


class SourceTag(str, Enum):
    EXPERIMENT = "experiment"
    LITERATURE = "literature"
    PROPOSED = "proposed"


class SuggestAlgorithm(str, Enum):
    LHS = "lhs"
    TREES = "trees"
    RIDGE = "ridge"
    RANDOM = "random"


class SuggestMode(str, Enum):
    """User-facing presets mapped to explore–exploit mix."""

    FAST = "fast"  # space-filling / random-feasible
    BALANCED = "balanced"  # trees + moderate explore
    EXPLOIT = "exploit"  # trees, low explore
    EXPLORE = "explore"  # trees, high explore
    RIDGE = "ridge"


MODE_TO_ALGORITHM: dict[SuggestMode, SuggestAlgorithm] = {
    SuggestMode.FAST: SuggestAlgorithm.LHS,
    SuggestMode.BALANCED: SuggestAlgorithm.TREES,
    SuggestMode.EXPLOIT: SuggestAlgorithm.TREES,
    SuggestMode.EXPLORE: SuggestAlgorithm.TREES,
    SuggestMode.RIDGE: SuggestAlgorithm.RIDGE,
}

MODE_TO_LAMBDA: dict[SuggestMode, float] = {
    SuggestMode.FAST: 1.0,
    SuggestMode.BALANCED: 0.5,
    SuggestMode.EXPLOIT: 0.1,
    SuggestMode.EXPLORE: 1.5,
    SuggestMode.RIDGE: 0.3,
}


@dataclass
class Factor:
    name: str
    type: FactorType = FactorType.CONTINUOUS
    bounds: tuple[float, float] | None = None
    levels: list[Any] | None = None
    unit: str | None = None
    role: FactorRole = FactorRole.FREE
    fixed_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        d["role"] = self.role.value
        if self.bounds is not None:
            d["bounds"] = list(self.bounds)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Factor:
        bounds = data.get("bounds")
        return cls(
            name=data["name"],
            type=FactorType(data.get("type", "continuous")),
            bounds=tuple(bounds) if bounds is not None else None,
            levels=data.get("levels"),
            unit=data.get("unit"),
            role=FactorRole(data.get("role", "free")),
            fixed_value=data.get("fixed_value"),
        )

    def validate(self) -> None:
        if not self.name or not str(self.name).strip():
            raise ValueError("Factor name must be non-empty")
        if self.type in (FactorType.CONTINUOUS, FactorType.INTEGER):
            if self.bounds is None or len(self.bounds) != 2:
                raise ValueError(f"Factor '{self.name}' needs bounds [low, high]")
            if self.bounds[0] > self.bounds[1]:
                raise ValueError(f"Factor '{self.name}' has inverted bounds")
        if self.type == FactorType.CATEGORICAL:
            if not self.levels:
                raise ValueError(f"Factor '{self.name}' needs levels")
        if self.type == FactorType.FIXED and self.fixed_value is None:
            if self.bounds is not None:
                self.fixed_value = self.bounds[0]
            elif self.levels:
                self.fixed_value = self.levels[0]
            else:
                raise ValueError(f"Fixed factor '{self.name}' needs a value")


@dataclass
class Response:
    name: str
    goal: ResponseGoal = ResponseGoal.MAXIMIZE
    bounds: tuple[float, float] | None = None
    unit: str | None = None
    target: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["goal"] = self.goal.value
        if self.bounds is not None:
            d["bounds"] = list(self.bounds)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Response:
        bounds = data.get("bounds")
        return cls(
            name=data["name"],
            goal=ResponseGoal(data.get("goal", "maximize")),
            bounds=tuple(bounds) if bounds is not None else None,
            unit=data.get("unit"),
            target=data.get("target"),
        )

    def validate(self) -> None:
        if not self.name or not str(self.name).strip():
            raise ValueError("Response name must be non-empty")


@dataclass
class CampaignSchema:
    factors: list[Factor] = field(default_factory=list)
    responses: list[Response] = field(default_factory=list)

    def factor_names(self) -> list[str]:
        return [f.name for f in self.factors]

    def response_names(self) -> list[str]:
        return [r.name for r in self.responses]

    def get_factor(self, name: str) -> Factor:
        for f in self.factors:
            if f.name == name:
                return f
        raise KeyError(f"Unknown factor: {name}")

    def get_response(self, name: str) -> Response:
        for r in self.responses:
            if r.name == name:
                return r
        raise KeyError(f"Unknown response: {name}")

    def validate(self) -> None:
        names = self.factor_names() + self.response_names()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate factor/response names are not allowed")
        for f in self.factors:
            f.validate()
        for r in self.responses:
            r.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "factors": [f.to_dict() for f in self.factors],
            "responses": [r.to_dict() for r in self.responses],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CampaignSchema:
        return cls(
            factors=[Factor.from_dict(f) for f in data.get("factors", [])],
            responses=[Response.from_dict(r) for r in data.get("responses", [])],
        )


@dataclass
class SuggestSettings:
    algorithm: SuggestAlgorithm = SuggestAlgorithm.TREES
    mode: SuggestMode = SuggestMode.BALANCED
    batch_size: int = 3
    seed: int = 42
    explore_lambda: float = 0.5
    n_candidates: int = 512
    n_min_for_model: int = 3
    active_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm.value,
            "mode": self.mode.value,
            "batch_size": self.batch_size,
            "seed": self.seed,
            "explore_lambda": self.explore_lambda,
            "n_candidates": self.n_candidates,
            "n_min_for_model": self.n_min_for_model,
            "active_response": self.active_response,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SuggestSettings:
        return cls(
            algorithm=SuggestAlgorithm(data.get("algorithm", "trees")),
            mode=SuggestMode(data.get("mode", "balanced")),
            batch_size=int(data.get("batch_size", 3)),
            seed=int(data.get("seed", 42)),
            explore_lambda=float(data.get("explore_lambda", 0.5)),
            n_candidates=int(data.get("n_candidates", 512)),
            n_min_for_model=int(data.get("n_min_for_model", 3)),
            active_response=data.get("active_response"),
        )

    def apply_mode(self, mode: SuggestMode) -> None:
        self.mode = mode
        self.algorithm = MODE_TO_ALGORITHM[mode]
        self.explore_lambda = MODE_TO_LAMBDA[mode]


@dataclass
class ColumnMapping:
    """Maps source columns to factor / response / meta roles."""

    factors: dict[str, str] = field(default_factory=dict)  # factor_name -> col
    responses: dict[str, str] = field(default_factory=dict)  # response_name -> col
    sample_id: str | None = None
    ignore: list[str] = field(default_factory=list)
    # optional type hints for auto-schema: name -> FactorType value
    factor_types: dict[str, str] = field(default_factory=dict)
    response_goals: dict[str, str] = field(default_factory=dict)
