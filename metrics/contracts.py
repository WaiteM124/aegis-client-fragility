"""Pydantic contracts for dependency graphs, shock scenarios, and metric results.

Aegis never predicts events. Scenarios here are structural stress probes
(which nodes or edges are shocked and by how much), not forecasts.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class NodeKind(str, Enum):
    SUPPLIER = "supplier"
    ASSET = "asset"
    ROUTE = "route"
    BUYER = "buyer"


class Status(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    # Explicit probe not configured — never treated as a pass / green.
    NOT_TESTED = "not_tested"


class NodeSpec(BaseModel):
    """A node in the dependency graph."""

    id: str
    kind: NodeKind
    # Optional monoculture attributes (ignored when absent)
    type: str | None = None
    region: str | None = None
    technology: str | None = None
    # Explicit criticality for SPOF status (not inferred).
    # A cut node on a critical flow (sole supplier, sole route, sole site
    # for a critical output) must be marked critical=true in the graph data.
    critical: bool = False
    # Extra free-form attributes preserved for loaders / diagnostics
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _lift_common_attrs(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        attrs = dict(data.get("attributes") or {})
        for key in ("type", "region", "technology"):
            if key in data and data[key] is not None:
                attrs.setdefault(key, data[key])
        data = {**data, "attributes": attrs}
        return data


class GraphInputSpec(BaseModel):
    """A named structural stress input (not a forecast).

    ``worst_on_record`` is the size of the largest move observed for this
    input — used only as a scan-grid anchor for convexity and distance-to-ruin.
    No likelihood is attached. Bounds clamp physically impossible values
    (e.g. demand below zero, supplier loss above 100%).
    """

    id: str
    worst_on_record: float | None = None
    lower_bound: float | None = 0.0
    upper_bound: float | None = 1.0


class RuinLineSpec(BaseModel):
    """Structural ruin thresholds for distance-to-ruin probes.

    Crossing any configured line is absorbing ruin. These are accounting
    floors, not event probabilities.
    """

    # Remaining deliverable-flow fraction of baseline below which is ruin.
    survival_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    # Optional named cause labels for reporting (which line broke).
    covenant_breach_flow_fraction: float | None = Field(default=None, ge=0.0, le=1.0)


class EdgeSpec(BaseModel):
    """A directed dependency edge: source feeds target.

    share  — fraction of the target's inbound supply carried on this edge
             (supplier→… edges into the buyer should sum ≈ 1.0 across paths)
    flow   — absolute flow units currently on the edge
    capacity — max flow the edge can carry
    buffer — inventory / time buffer attached to the edge (same units as flow)
    stress_response — optional ladder profile: buffered|linear|decelerating|cliff
    """

    source: str
    target: str
    share: float = Field(ge=0.0, le=1.0, default=0.0)
    flow: float = Field(ge=0.0, default=0.0)
    capacity: float = Field(ge=0.0, default=0.0)
    buffer: float = Field(ge=0.0, default=0.0)
    stress_response: str | None = None

    @field_validator("capacity")
    @classmethod
    def _capacity_covers_flow_hint(cls, v: float, info: Any) -> float:
        # Soft: allow capacity < flow so under-buffered graphs can be described;
        # slack metric will flag it.
        return v


class DependencyGraphSpec(BaseModel):
    """YAML-serialisable dependency graph input."""

    name: str = "unnamed"
    nodes: list[NodeSpec]
    edges: list[EdgeSpec]
    # Optional explicit client/buyer id; otherwise inferred as the sole buyer
    client_id: str | None = None
    # Client-level ruin floor: remaining flow fraction of F0 below which is ruin.
    # When omitted, metrics.thresholds.RuinThresholds.survival_floor (default 0.5) applies.
    survival_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    # Named stress inputs with worst-on-record anchors (convexity / distance-to-ruin).
    inputs: list[GraphInputSpec] = Field(default_factory=list)
    # Explicit ruin lines for distance-to-ruin (survival floor / covenant).
    ruin_line: RuinLineSpec | None = None

    @model_validator(mode="after")
    def _resolve_client(self) -> DependencyGraphSpec:
        buyers = [n.id for n in self.nodes if n.kind == NodeKind.BUYER]
        if self.client_id is None:
            if len(buyers) == 1:
                object.__setattr__(self, "client_id", buyers[0])
            elif len(buyers) == 0:
                raise ValueError("graph has no buyer node and no client_id")
            else:
                raise ValueError(
                    "multiple buyers; set client_id explicitly to the client node"
                )
        else:
            ids = {n.id for n in self.nodes}
            if self.client_id not in ids:
                raise ValueError(f"client_id {self.client_id!r} not in nodes")
        return self


class NodeShock(BaseModel):
    """Shock a node: remove or degrade its throughput by `intensity` in [0, 1]."""

    node_id: str
    intensity: float = Field(ge=0.0, le=1.0, default=1.0)


class EdgeShock(BaseModel):
    """Shock an edge: reduce its flow/capacity by `intensity` in [0, 1]."""

    source: str
    target: str
    intensity: float = Field(ge=0.0, le=1.0, default=1.0)


class Scenario(BaseModel):
    """A structural stress probe — not a forecast.

    Omitting shocks means structural metrics that need an explicit probe
    (notably ruin) return NOT_TESTED rather than silently assuming a
    default ladder. Silence is not safety.
    """

    name: str = "default"
    node_shocks: list[NodeShock] = Field(default_factory=list)
    edge_shocks: list[EdgeShock] = Field(default_factory=list)
    # Optional override for ruin / convexity survival floor
    survival_floor: float | None = None
    # Opt-in: run the documented stress ladder as an explicit probe.
    # Required for ruin to leave NOT_TESTED when no node/edge shocks are set.
    run_stress_ladder: bool = False
    # Optional override of ladder intensities when run_stress_ladder is true.
    stress_ladder: list[float] | None = None


class MetricResult(BaseModel):
    """Standard result envelope for every structural metric."""

    metric: str
    version: str
    value: float
    status: Status
    # Nodes / edges that drove the reading
    drivers: list[str] = Field(default_factory=list)
    # Inputs used (shares, ladder losses, path counts, …)
    inputs: dict[str, Any] = Field(default_factory=dict)
    # Plain-English summary; must not claim prediction
    meaning: str = ""
    unit: str | None = None

    def format_readable(self) -> str:
        drivers = ", ".join(self.drivers) if self.drivers else "(none)"
        lines = [
            f"metric : {self.metric} v{self.version}",
            f"value  : {self.value}",
            f"status : {self.status.value.upper()}",
            f"drivers: {drivers}",
        ]
        if self.meaning:
            lines.append(f"meaning: {self.meaning}")
        if self.inputs:
            pretty = ", ".join(f"{k}={v}" for k, v in self.inputs.items())
            lines.append(f"inputs : {pretty}")
        return "\n".join(lines)


StatusLiteral = Literal["green", "amber", "red", "not_tested"]
