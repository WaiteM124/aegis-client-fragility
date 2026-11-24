"""Aegis structural-fragility metrics.

These metrics find structural weaknesses in a client's dependency graph.
They do not forecast events, estimate probabilities, or fit historical tails.
"""

from metrics.contracts import MetricResult, Scenario, Status
from metrics.thresholds import THRESHOLDS

__all__ = ["MetricResult", "Scenario", "Status", "THRESHOLDS"]
