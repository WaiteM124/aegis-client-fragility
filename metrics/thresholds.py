"""Configurable default status thresholds for structural-fragility metrics.

Status meanings (shared across metrics):
  green      — structurally diversified / buffered / optional relative to the metric
  amber      — material structural weakness present
  red        — severe structural weakness; for ruin, a hard point-of-no-return flag
  not_tested — explicit probe / required data missing; never counted as a pass

Thresholds are structural cut-points, not probabilities or forecasts.
Override by editing this module or passing custom Thresholds into compute().
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HHIThresholds:
    """HHI = Σ s_i² over supplier shares. High = concentrated."""

    # green if value <= green_max; amber if <= amber_max; else red
    green_max: float = 0.25  # four equal suppliers or better
    amber_max: float = 0.50  # two equal suppliers territory


@dataclass(frozen=True)
class MonocultureThresholds:
    """Max attribute-bucket share. High = monoculture."""

    green_max: float = 0.40
    amber_max: float = 0.70


@dataclass(frozen=True)
class SpofThresholds:
    """Single points of failure.

    Status is driven by criticality (explicit on graph nodes), not raw count:
      green  — no cut nodes
      amber  — cut node(s) only on non-critical paths
      red    — any cut node marked critical (sole supplier / sole critical route / …)
    """

    # Retained for diagnostics; status no longer uses count cut-offs alone.
    green_max: int = 0
    amber_max: int = 1


@dataclass(frozen=True)
class CascadeDepthThresholds:
    """Longest cascade hop count. High = deep contagion reach."""

    green_max: int = 1
    amber_max: int = 3


@dataclass(frozen=True)
class ConvexityThresholds:
    """Harm curvature via symmetric second differences on model output.

    Clearly positive curvature → fragile (harm accelerates).
    Near zero → robust.
    Clearly negative → antifragile (own flag; not merely green).

    Step sizes are multiples of each input's worst-on-record move.
    No likelihoods are attached to the scan grid.
    """

    version: str = "2.0.0"
    # |curvature| below this → treat as linear / robust
    linear_tol: float = 1e-6
    # fragile if mean curvature > amber_min; red if > red_min (scaled by F0)
    amber_min: float = 1e-6
    red_min: float = 0.05
    # Relative jump between neighbouring scan steps that counts as a cliff
    cliff_rel_jump: float = 0.35
    # Scan-grid multiples of worst-on-record (step sizes d, not scenarios)
    step_multiples: tuple[float, ...] = (0.25, 0.5, 1.0, 1.5, 2.0)


@dataclass(frozen=True)
class RuinThresholds:
    """Ruin is binary when tested: any ladder rung that crosses the floor is red.

    Without an explicit shock / stress-ladder probe, ruin returns NOT_TESTED
    (silence is not safety).

    survival_floor is the minimum remaining deliverable-flow *fraction*
    of baseline F₀ the client can tolerate. Default 0.5: the client is
    treated as past the point of no return once remaining flow falls
    strictly below half of baseline (a client is usually finished well
    before total loss). Override per graph via YAML ``survival_floor``,
    via ``Scenario.survival_floor``, or ``--survival-floor`` on the CLI.
    """

    survival_floor: float = 0.5


@dataclass(frozen=True)
class DistanceToRuinThresholds:
    """Per-input distance to ruin in multiples of worst-on-record.

    Cut-offs are versioned here — not hard-coded in the metric module.
    Status is per input; never averaged across inputs.
      red    — ruin multiple <= red_max_multiple
      amber  — ruin multiple <= amber_max_multiple
      green  — ruin beyond amber_max_multiple (or no ruin in scan range → green
               only when the scan completed; missing data → not_tested)
    """

    version: str = "1.0.0"
    red_max_multiple: float = 1.0
    amber_max_multiple: float = 2.0
    scan_max_multiple: float = 5.0
    scan_multiples: tuple[float, ...] = (
        0.25,
        0.5,
        0.75,
        1.0,
        1.25,
        1.5,
        1.75,
        2.0,
        2.5,
        3.0,
        4.0,
        5.0,
    )
    bisection_iterations: int = 40


@dataclass(frozen=True)
class OptionalityThresholds:
    """Node-disjoint supply-path count. High = more ways out."""

    # green if value >= green_min; amber if >= amber_min; else red
    green_min: int = 2
    amber_min: int = 1


@dataclass(frozen=True)
class SlackThresholds:
    """Spare capacity + buffer relative to flow. High = more slack."""

    green_min: float = 0.25
    amber_min: float = 0.10


@dataclass(frozen=True)
class RunwayThresholds:
    """Liquidity runway in months. Low = fragile cash structure.

    red    if runway_months < red_max_months
    amber  if runway_months < amber_max_months
    green  otherwise (when fully specified)
    """

    version: str = "1.0.0"
    red_max_months: float = 3.0
    amber_max_months: float = 6.0


@dataclass(frozen=True)
class EnergyMarginThresholds:
    """Unrecovered energy cost share linked to margin.

    red    if unrecovered_share > red_min
    amber  if unrecovered_share > amber_min
    green  otherwise (when fully specified)
    """

    version: str = "1.0.0"
    amber_min: float = 0.05
    red_min: float = 0.15


@dataclass(frozen=True)
class Thresholds:
    hhi: HHIThresholds = field(default_factory=HHIThresholds)
    monoculture: MonocultureThresholds = field(default_factory=MonocultureThresholds)
    spof: SpofThresholds = field(default_factory=SpofThresholds)
    cascade_depth: CascadeDepthThresholds = field(default_factory=CascadeDepthThresholds)
    convexity: ConvexityThresholds = field(default_factory=ConvexityThresholds)
    ruin: RuinThresholds = field(default_factory=RuinThresholds)
    distance_to_ruin: DistanceToRuinThresholds = field(
        default_factory=DistanceToRuinThresholds
    )
    optionality: OptionalityThresholds = field(default_factory=OptionalityThresholds)
    slack: SlackThresholds = field(default_factory=SlackThresholds)
    runway: RunwayThresholds = field(default_factory=RunwayThresholds)
    energy_margin: EnergyMarginThresholds = field(
        default_factory=EnergyMarginThresholds
    )


THRESHOLDS = Thresholds()

# Default stress-ladder shock intensities (fraction of edge flow removed)
STRESS_LADDER: tuple[float, ...] = (0.10, 0.20, 0.50)
