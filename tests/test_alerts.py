"""Tests for the threshold alert system (rc_insights.alerts)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from rc_insights.alerts import VALID_OPERATORS, AlertEngine, AlertRule

# ---------------------------------------------------------------------------
# AlertRule
# ---------------------------------------------------------------------------


class TestAlertRule:
    def test_valid_operators_accepted(self):
        for op in VALID_OPERATORS:
            rule = AlertRule(metric="churn", operator=op, threshold=5.0)
            assert rule.operator == op

    def test_invalid_operator_raises(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            AlertRule(metric="churn", operator="neq", threshold=5.0)

    def test_default_message_is_none(self):
        rule = AlertRule(metric="mrr", operator="gt", threshold=1000.0)
        assert rule.message is None

    def test_custom_message_stored(self):
        rule = AlertRule(metric="churn", operator="gt", threshold=8.0, message="Too high!")
        assert rule.message == "Too high!"


# ---------------------------------------------------------------------------
# AlertEngine.evaluate — operator correctness
# ---------------------------------------------------------------------------


class TestAlertEngineEvaluate:
    def _engine(self, **kwargs) -> AlertEngine:
        """Return an engine with a single rule built from kwargs."""
        return AlertEngine([AlertRule(**kwargs)])

    def test_gt_triggers_above(self):
        engine = self._engine(metric="churn", operator="gt", threshold=8.0)
        results = engine.evaluate({"churn": 9.0})
        assert len(results) == 1
        assert results[0].triggered is True

    def test_gt_no_trigger_at_equal(self):
        engine = self._engine(metric="churn", operator="gt", threshold=8.0)
        results = engine.evaluate({"churn": 8.0})
        assert results[0].triggered is False

    def test_lt_triggers_below(self):
        engine = self._engine(metric="trial_conversion", operator="lt", threshold=40.0)
        results = engine.evaluate({"trial_conversion": 35.0})
        assert results[0].triggered is True

    def test_lt_no_trigger_above(self):
        engine = self._engine(metric="trial_conversion", operator="lt", threshold=40.0)
        results = engine.evaluate({"trial_conversion": 50.0})
        assert results[0].triggered is False

    def test_gte_triggers_at_equal(self):
        engine = self._engine(metric="churn", operator="gte", threshold=8.0)
        results = engine.evaluate({"churn": 8.0})
        assert results[0].triggered is True

    def test_lte_triggers_at_equal(self):
        engine = self._engine(metric="mrr", operator="lte", threshold=5000.0)
        results = engine.evaluate({"mrr": 5000.0})
        assert results[0].triggered is True

    def test_change_pct_triggers_on_large_drop(self):
        """change_pct fires when abs(value) >= abs(threshold)."""
        engine = self._engine(metric="mrr_change_pct", operator="change_pct", threshold=10.0)
        results = engine.evaluate({"mrr_change_pct": -12.0})
        assert results[0].triggered is True

    def test_change_pct_triggers_on_large_gain(self):
        engine = self._engine(metric="mrr_change_pct", operator="change_pct", threshold=10.0)
        results = engine.evaluate({"mrr_change_pct": 15.0})
        assert results[0].triggered is True

    def test_change_pct_no_trigger_small_change(self):
        engine = self._engine(metric="mrr_change_pct", operator="change_pct", threshold=10.0)
        results = engine.evaluate({"mrr_change_pct": -5.0})
        assert results[0].triggered is False

    def test_missing_metric_skipped(self):
        """A rule whose metric key is absent must be silently skipped."""
        engine = self._engine(metric="trial_conversion", operator="lt", threshold=40.0)
        results = engine.evaluate({"churn": 7.5})
        assert results == []

    def test_returns_all_alerts_including_passing(self):
        engine = AlertEngine([
            AlertRule(metric="churn", operator="gt", threshold=8.0),
            AlertRule(metric="mrr", operator="lt", threshold=1000.0),
        ])
        results = engine.evaluate({"churn": 9.0, "mrr": 5000.0})
        assert len(results) == 2
        triggered = [a for a in results if a.triggered]
        passing = [a for a in results if not a.triggered]
        assert len(triggered) == 1
        assert len(passing) == 1

    def test_current_value_stored(self):
        engine = self._engine(metric="churn", operator="gt", threshold=8.0)
        result = engine.evaluate({"churn": 9.5})[0]
        assert result.current_value == pytest.approx(9.5)

    def test_auto_generated_message_contains_metric(self):
        engine = self._engine(metric="churn", operator="gt", threshold=8.0)
        result = engine.evaluate({"churn": 9.5})[0]
        assert "churn" in result.message
        assert "9.50" in result.message
        assert "8.00" in result.message

    def test_custom_message_overrides_auto(self):
        engine = AlertEngine([
            AlertRule(metric="churn", operator="gt", threshold=8.0, message="Custom msg")
        ])
        result = engine.evaluate({"churn": 10.0})[0]
        assert result.message == "Custom msg"

    def test_empty_metrics_returns_empty(self):
        engine = AlertEngine.default_rules()
        results = engine.evaluate({})
        assert results == []


# ---------------------------------------------------------------------------
# AlertEngine.default_rules
# ---------------------------------------------------------------------------


class TestDefaultRules:
    def test_has_three_rules(self):
        engine = AlertEngine.default_rules()
        assert len(engine.rules) == 3

    def test_churn_rule_fires(self):
        engine = AlertEngine.default_rules()
        triggered = [
            a for a in engine.evaluate({"churn": 9.0}) if a.triggered
        ]
        assert any(a.rule.metric == "churn" for a in triggered)

    def test_mrr_change_rule_fires_on_drop(self):
        engine = AlertEngine.default_rules()
        triggered = [
            a for a in engine.evaluate({"mrr_change_pct": -15.0}) if a.triggered
        ]
        assert any(a.rule.metric == "mrr_change_pct" for a in triggered)

    def test_mrr_change_rule_no_fire_on_small_drop(self):
        engine = AlertEngine.default_rules()
        triggered = [
            a for a in engine.evaluate({"mrr_change_pct": -5.0}) if a.triggered
        ]
        assert not any(a.rule.metric == "mrr_change_pct" for a in triggered)

    def test_trial_conversion_rule_fires(self):
        engine = AlertEngine.default_rules()
        triggered = [
            a for a in engine.evaluate({"trial_conversion": 30.0}) if a.triggered
        ]
        assert any(a.rule.metric == "trial_conversion" for a in triggered)

    def test_no_alerts_for_healthy_metrics(self):
        engine = AlertEngine.default_rules()
        healthy = {
            "churn": 3.0,
            "mrr_change_pct": 5.0,
            "trial_conversion": 60.0,
        }
        triggered = [a for a in engine.evaluate(healthy) if a.triggered]
        assert triggered == []


# ---------------------------------------------------------------------------
# AlertEngine.from_yaml
# ---------------------------------------------------------------------------


class TestFromYaml:
    def _write_yaml(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "alerts.yml"
        p.write_text(textwrap.dedent(content))
        return p

    def test_loads_single_rule(self, tmp_path):
        cfg = self._write_yaml(tmp_path, """
            rules:
              - metric: churn
                operator: gt
                threshold: 5.0
        """)
        engine = AlertEngine.from_yaml(str(cfg))
        assert len(engine.rules) == 1
        assert engine.rules[0].metric == "churn"
        assert engine.rules[0].operator == "gt"
        assert engine.rules[0].threshold == pytest.approx(5.0)

    def test_loads_multiple_rules(self, tmp_path):
        cfg = self._write_yaml(tmp_path, """
            rules:
              - metric: churn
                operator: gt
                threshold: 8.0
              - metric: mrr_change_pct
                operator: lt
                threshold: -10.0
              - metric: trial_conversion
                operator: lt
                threshold: 40.0
        """)
        engine = AlertEngine.from_yaml(str(cfg))
        assert len(engine.rules) == 3

    def test_loads_custom_message(self, tmp_path):
        cfg = self._write_yaml(tmp_path, """
            rules:
              - metric: churn
                operator: gt
                threshold: 5.0
                message: "Churn is too high!"
        """)
        engine = AlertEngine.from_yaml(str(cfg))
        assert engine.rules[0].message == "Churn is too high!"

    def test_empty_rules_list(self, tmp_path):
        cfg = self._write_yaml(tmp_path, "rules: []\n")
        engine = AlertEngine.from_yaml(str(cfg))
        assert engine.rules == []

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            AlertEngine.from_yaml(str(tmp_path / "missing.yml"))

    def test_invalid_operator_raises(self, tmp_path):
        cfg = self._write_yaml(tmp_path, """
            rules:
              - metric: churn
                operator: bad_op
                threshold: 5.0
        """)
        with pytest.raises(ValueError, match="Unknown operator"):
            AlertEngine.from_yaml(str(cfg))

    def test_evaluate_after_yaml_load(self, tmp_path):
        cfg = self._write_yaml(tmp_path, """
            rules:
              - metric: churn
                operator: gt
                threshold: 8.0
        """)
        engine = AlertEngine.from_yaml(str(cfg))
        results = engine.evaluate({"churn": 12.0})
        assert results[0].triggered is True

    def test_example_yml_is_valid(self):
        """The bundled alerts.example.yml must parse without errors."""
        example = Path(__file__).parent.parent / "alerts.example.yml"
        if not example.exists():
            pytest.skip("alerts.example.yml not found")
        engine = AlertEngine.from_yaml(str(example))
        assert len(engine.rules) > 0
