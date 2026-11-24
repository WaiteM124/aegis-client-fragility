"""Configurable default status thresholds for structural-fragility metrics.

Status meanings (shared across metrics):
  green — structurally diversified / buffered / optional relative to the metric
  amber — material structural weakness present
  red   — severe structural weakness; for ruin, a hard point-of-no-return flag

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
    """Count of single points of failure. Any SPOF is at least amber."""

    green_max: int = 0
    amber_max: int = 1  # exactly one SPOF → amber; more → red


@dataclass(frozen=True)
class CascadeDepthThresholds:
    """Longest cascade hop count. High = deep contagion reach."""

    green_max: int = 1
    amber_max: int = 3


@dataclass(frozen=True)
class ConvexityThresholds:
    """Acceleration of loss under the stress ladder (second differences).

    Positive acceleration (concave payoff) → fragile → red/amber.
    Near-zero → robust → green.
    Negative (convex payoff / antifragile) → green.
    """

    # |acceleration| below this → treat as linear / robust
    linear_tol: float = 1e-9
    # fragile if acceleration > amber_min; red if > red_min
    amber_min: float = 1e-9
    red_min: float = 0.05


@dataclass(frozen=True)
class RuinThresholds:
    """Ruin is binary: any ladder rung that crosses the floor is red.

    survival_floor is the minimum remaining deliverable-flow *fraction*
    of baseline F₀ the client can tolerate. Default 0.5: the client is
    treated as past the point of no return once remaining flow falls
    strictly below half of baseline (a client is usually finished well
    before total loss). Override per graph via YAML ``survival_floor``,
    via ``Scenario.survival_floor``, or ``--survival-floor`` on the CLI.
    """

    survival_floor: float = 0.5


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
class Thresholds:
    hhi: HHIThresholds = field(default_factory=HHIThresholds)
    monoculture: MonocultureThresholds = field(default_factory=MonocultureThresholds)
    spof: SpofThresholds = field(default_factory=SpofThresholds)
    cascade_depth: CascadeDepthThresholds = field(default_factory=CascadeDepthThresholds)
    convexity: ConvexityThresholds = field(default_factory=ConvexityThresholds)
    ruin: RuinThresholds = field(default_factory=RuinThresholds)
    optionality: OptionalityThresholds = field(default_factory=OptionalityThresholds)
    slack: SlackThresholds = field(default_factory=SlackThresholds)


THRESHOLDS = Thresholds()

# Default stress-ladder shock intensities (fraction of edge flow removed)
STRESS_LADDER: tuple[float, ...] = (0.10, 0.20, 0.50)
