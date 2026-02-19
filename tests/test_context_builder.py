"""Tests for the LLM context assembly helpers."""

from __future__ import annotations

from agent_deploy.llm.context import (
    build_analysis_context,
    build_changelog_context,
    format_alert_list,
    format_metrics_table,
    format_slo_table,
)


def test_build_analysis_context(sample_state):
    """Verify all expected sections are present in the analysis context."""
    ctx = build_analysis_context(sample_state)

    assert "## Deploy Context" in ctx
    assert "payments-api" in ctx
    assert "v1.2.3" in ctx
    assert "us-east-1" in ctx

    assert "## What Changed" in ctx
    assert "handle timeout" in ctx
    assert "### High-Risk Changes" in ctx
    assert "Database migration" in ctx

    assert "## Observability" in ctx
    assert "### Alerts" in ctx
    assert "### SLO Status" in ctx
    assert "### Golden Signals" in ctx


def test_build_changelog_context():
    """Verify commits and diff sections are present."""
    diff = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new"
    commits = [
        {"sha": "abc12345de", "message": "fix: handle timeout\nMore details here"},
        {"sha": "def67890ab", "message": "feat: add retry logic"},
    ]

    ctx = build_changelog_context(diff, commits)

    assert "## Commits" in ctx
    assert "abc12345" in ctx
    assert "fix: handle timeout" in ctx
    assert "def67890" in ctx
    assert "feat: add retry logic" in ctx

    assert "## Diff" in ctx
    assert "```diff" in ctx
    assert "-old" in ctx
    assert "+new" in ctx


def test_build_changelog_context_empty():
    """Empty diff and commits should not crash."""
    ctx = build_changelog_context("", [])
    assert "## Commits" in ctx
    assert "No commit data available." in ctx
    assert "(empty diff)" in ctx


def test_format_metrics_table():
    """Verify the metrics table has correct headers, rows, and deltas."""
    baseline = {
        "latency_p50": 42.0,
        "latency_p99": 180.0,
        "error_rate": 0.1,
        "request_rate": 1000.0,
        "cpu_utilization": 60.0,
        "memory_utilization": 70.0,
    }
    current = {
        "latency_p50": 45.0,
        "latency_p99": 200.0,
        "error_rate": 0.5,
        "request_rate": 1200.0,
        "cpu_utilization": 65.0,
        "memory_utilization": 72.0,
    }

    table = format_metrics_table(baseline, current)

    assert "| Metric | Baseline | Current | Delta |" in table
    assert "Latency p50" in table
    assert "Latency p99" in table
    assert "Error rate" in table
    assert "+3.00" in table  # latency_p50 delta
    assert "+0.40" in table  # error_rate delta


def test_format_metrics_table_partial():
    """Missing keys should be skipped gracefully."""
    baseline = {"latency_p50": 42.0}
    current = {"latency_p50": 45.0}

    table = format_metrics_table(baseline, current)
    assert "Latency p50" in table
    # Metrics not present in either dict should not appear
    assert "Error rate" not in table


def test_format_alert_list():
    """Verify alert formatting with severity, name, and message."""
    alerts = [
        {"name": "HighErrorRate", "severity": "critical", "message": "Error rate > 5%"},
        {"name": "LatencySpike", "severity": "high", "message": "p99 > 500ms", "since": "10m ago"},
    ]

    result = format_alert_list(alerts)

    assert "**[CRITICAL]** HighErrorRate" in result
    assert "Error rate > 5%" in result
    assert "**[HIGH]** LatencySpike" in result
    assert "(since 10m ago)" in result


def test_format_alert_list_empty():
    """Empty alert list should return 'No alerts firing.'."""
    assert format_alert_list([]) == "No alerts firing."


def test_format_slo_table():
    """Verify SLO table structure."""
    slos = [
        {"name": "availability", "target": "99.9%", "current": "99.85%", "budget_remaining": "15%"},
        {"name": "latency", "target": "200ms", "current": "180ms", "budget_remaining": "60%"},
    ]

    table = format_slo_table(slos)

    assert "| SLO | Target | Current | Budget Remaining |" in table
    assert "availability" in table
    assert "99.85%" in table
    assert "latency" in table
    assert "60%" in table


def test_empty_state_handling():
    """An empty/minimal state should not crash build_analysis_context."""
    ctx = build_analysis_context({})

    assert "## Deploy Context" in ctx
    assert "unknown" in ctx
    assert "No alerts firing." in ctx
    assert "No SLO data available." in ctx
