"""Threshold alert system for RC Insights.

Provides a configurable alert engine that evaluates subscription metrics
against user-defined rules loaded from YAML or using sensible defaults.

Usage:
    engine = AlertEngine.default_rules()
    alerts = engine.evaluate({"churn": 9.5, "mrr_change_pct": -12.0})
    for alert in alerts:
        if alert.triggered:
            print(f"🚨 {alert.message}")
"""

from __future__ import annotations

import operator as _op
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Operator registry
# ---------------------------------------------------------------------------

_OP_FN: dict[str, Callable[[float, float], bool]] = {
    "gt": _op.gt,
    "lt": _op.lt,
    "gte": _op.ge,
    "lte": _op.le,
    # change_pct: fires when the absolute percentage change meets or exceeds threshold.
    # Use with metrics that represent a percentage change (e.g. mrr_change_pct = -12.0).
    "change_pct": lambda v, t: abs(v) >= abs(t),
}

_OP_SYMBOL: dict[str, str] = {
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
    "change_pct": "changed ≥",
}

VALID_OPERATORS: list[str] = list(_OP_FN)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AlertRule:
    """A single alert rule definition.

    Attributes:
        metric:    Key in the metrics dict to check (e.g. "churn", "mrr_change_pct").
        operator:  Comparison operator: "gt", "lt", "gte", "lte", or "change_pct".
        threshold: Value to compare against.
        message:   Optional custom message. Auto-generated from rule if None.
    """

    metric: str
    operator: str
    threshold: float
    message: str | None = None

    def __post_init__(self) -> None:
        if self.operator not in VALID_OPERATORS:
            raise ValueError(
                f"Unknown operator '{self.operator}'. Valid: {VALID_OPERATORS}"
            )


@dataclass
class Alert:
    """Result of evaluating a single AlertRule against a metrics snapshot.

    Attributes:
        rule:          The rule that was evaluated.
        current_value: Metric value at evaluation time.
        triggered:     True when the rule condition was met.
        message:       Human-readable description (uses rule.message or auto-generated).
    """

    rule: AlertRule
    current_value: float
    triggered: bool
    message: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AlertEngine:
    """Evaluates a collection of AlertRules against a metrics snapshot.

    Example:
        engine = AlertEngine.default_rules()
        results = engine.evaluate({"churn": 9.5, "mrr_change_pct": -15.0})
        triggered = [a for a in results if a.triggered]
    """

    def __init__(self, rules: list[AlertRule]) -> None:
        self.rules = rules

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, metrics: dict[str, float]) -> list[Alert]:
        """Check all rules against *metrics*, return Alert for each matching rule.

        Rules whose metric key is absent from *metrics* are silently skipped
        (metric data not available — not an error).

        Args:
            metrics: Dict mapping metric name → current numeric value.

        Returns:
            List of Alert objects (both triggered and passing).
        """
        alerts: list[Alert] = []

        for rule in self.rules:
            if rule.metric not in metrics:
                continue

            value = metrics[rule.metric]
            compare_fn = _OP_FN[rule.operator]
            triggered = compare_fn(value, rule.threshold)

            if rule.message:
                msg = rule.message
            else:
                symbol = _OP_SYMBOL.get(rule.operator, rule.operator)
                msg = (
                    f"{rule.metric} is {value:.2f} "
                    f"(threshold: {symbol} {rule.threshold:.2f})"
                )

            alerts.append(
                Alert(
                    rule=rule,
                    current_value=value,
                    triggered=triggered,
                    message=msg,
                )
            )

        return alerts

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str) -> AlertEngine:
        """Load alert rules from a YAML config file.

        Expected format::

            rules:
              - metric: churn
                operator: gt
                threshold: 8.0
                message: "Churn too high!"   # optional

        Args:
            path: Path to the YAML config file.

        Returns:
            AlertEngine populated with rules from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            KeyError: If a required field (metric/operator/threshold) is missing.
            ValueError: If an invalid operator is specified.
        """
        with open(path) as fh:
            data: dict[str, Any] = yaml.safe_load(fh) or {}

        rules: list[AlertRule] = []
        for entry in data.get("rules", []):
            rules.append(
                AlertRule(
                    metric=str(entry["metric"]),
                    operator=str(entry["operator"]),
                    threshold=float(entry["threshold"]),
                    message=entry.get("message"),
                )
            )

        return cls(rules)

    @classmethod
    def default_rules(cls) -> AlertEngine:
        """Return an engine with sensible subscription health defaults.

        Default rules:
        - Churn rate > 8 %
        - MRR percent change < −10 % (i.e. MRR dropped more than 10 %)
        - Trial-to-paid conversion < 40 %
        """
        rules: list[AlertRule] = [
            AlertRule(
                metric="churn",
                operator="gt",
                threshold=8.0,
                message=None,  # auto-generated
            ),
            AlertRule(
                metric="mrr_change_pct",
                operator="lt",
                threshold=-10.0,
                message=None,  # auto-generated
            ),
            AlertRule(
                metric="trial_conversion",
                operator="lt",
                threshold=40.0,
                message=None,  # auto-generated
            ),
        ]
        return cls(rules)
