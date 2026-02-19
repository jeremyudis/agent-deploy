"""Context assembly helpers for LLM calls.

These functions transform raw state data into structured text prompts
following a tiered format: deploy context, changelog, observability
signals (alerts -> SLOs -> golden signals -> previous regions).
"""

from __future__ import annotations


def build_analysis_context(state: dict) -> str:
    """Assemble the structured context string for deploy-health analysis.

    Follows a tiered layout so the LLM sees the cheapest signals first:
      1. Deploy context (service, version, region)
      2. What changed (changelog + high-risk flags)
      3. Observability — alerts, SLOs, golden signals, previous regions
    """
    parts: list[str] = []

    # --- Deploy Context ---
    parts.append("## Deploy Context")
    parts.append(f"- Service: {state.get('service', 'unknown')}")
    parts.append(f"- Version: {state.get('version', 'unknown')}")
    parts.append(f"- Region: {state.get('current_region', 'unknown')}")
    parts.append(f"- Deploy ID: {state.get('deploy_id', 'unknown')}")
    parts.append("")

    # --- What Changed ---
    parts.append("## What Changed")
    changelog = state.get("changelog_summary", "No changelog available.")
    parts.append(changelog)
    high_risk = state.get("high_risk_changes", [])
    if high_risk:
        parts.append("")
        parts.append("### High-Risk Changes")
        for entry in high_risk:
            parts.append(f"- {entry}")
    parts.append("")

    # --- Observability ---
    parts.append("## Observability")

    # Alerts (tier 1 — cheapest signal)
    alerts = state.get("alerts_fired", [])
    parts.append("### Alerts")
    if alerts:
        parts.append(format_alert_list(alerts))
    else:
        parts.append("No alerts firing.")
    parts.append("")

    # SLOs (tier 2)
    baseline = state.get("baseline_snapshot", {})
    slos = baseline.get("slos", [])
    parts.append("### SLO Status")
    if slos:
        parts.append(format_slo_table(slos))
    else:
        parts.append("No SLO data available.")
    parts.append("")

    # Golden signals (tier 3)
    snapshots = state.get("monitoring_snapshots", [])
    current_snapshot = snapshots[-1] if snapshots else {}
    parts.append("### Golden Signals (Baseline vs Current)")
    if baseline and current_snapshot:
        parts.append(format_metrics_table(baseline, current_snapshot))
    else:
        parts.append("Insufficient data for comparison.")
    parts.append("")

    # Previous regions (tier 4 — cross-region context)
    completed = state.get("regions_completed", [])
    if completed:
        parts.append("### Previous Regions")
        for region in completed:
            parts.append(f"- {region}: completed")
    parts.append("")

    return "\n".join(parts)


def build_changelog_context(diff: str, commits: list[dict]) -> str:
    """Assemble context for changelog generation.

    Args:
        diff: The raw git diff text.
        commits: A list of commit dicts, each with at least "sha" and "message".
    """
    parts: list[str] = []

    parts.append("## Commits")
    if commits:
        for c in commits:
            sha = c.get("sha", "unknown")[:8]
            msg = c.get("message", "").split("\n", 1)[0]
            parts.append(f"- {sha}: {msg}")
    else:
        parts.append("No commit data available.")
    parts.append("")

    parts.append("## Diff")
    parts.append("```diff")
    parts.append(diff if diff else "(empty diff)")
    parts.append("```")

    return "\n".join(parts)


def format_metrics_table(baseline: dict, current: dict) -> str:
    """Format a before/after golden-signals comparison table.

    Expects each dict to contain keys like "latency_p50", "latency_p99",
    "error_rate", "request_rate", "cpu_utilization", etc.
    """
    metrics = [
        ("Latency p50 (ms)", "latency_p50"),
        ("Latency p99 (ms)", "latency_p99"),
        ("Error rate (%)", "error_rate"),
        ("Request rate (rps)", "request_rate"),
        ("CPU utilization (%)", "cpu_utilization"),
        ("Memory utilization (%)", "memory_utilization"),
    ]

    lines: list[str] = []
    lines.append("| Metric | Baseline | Current | Delta |")
    lines.append("|--------|----------|---------|-------|")

    for label, key in metrics:
        base_val = baseline.get(key)
        curr_val = current.get(key)
        if base_val is None and curr_val is None:
            continue
        base_str = f"{base_val}" if base_val is not None else "n/a"
        curr_str = f"{curr_val}" if curr_val is not None else "n/a"
        if isinstance(base_val, (int, float)) and isinstance(curr_val, (int, float)):
            delta = curr_val - base_val
            sign = "+" if delta >= 0 else ""
            delta_str = f"{sign}{delta:.2f}"
        else:
            delta_str = "-"
        lines.append(f"| {label} | {base_str} | {curr_str} | {delta_str} |")

    return "\n".join(lines)


def format_alert_list(alerts: list[dict]) -> str:
    """Format a list of alert dicts into a readable bulleted list.

    Each alert dict should have at least "name" and "severity". Optional
    keys: "message", "since".
    """
    if not alerts:
        return "No alerts firing."

    lines: list[str] = []
    for alert in alerts:
        name = alert.get("name", "unnamed")
        severity = alert.get("severity", "unknown")
        message = alert.get("message", "")
        since = alert.get("since", "")
        line = f"- **[{severity.upper()}]** {name}"
        if message:
            line += f" — {message}"
        if since:
            line += f" (since {since})"
        lines.append(line)
    return "\n".join(lines)


def format_slo_table(slos: list[dict]) -> str:
    """Format SLO status into a markdown table.

    Each SLO dict should have "name", "target", "current", and optionally
    "budget_remaining".
    """
    lines: list[str] = []
    lines.append("| SLO | Target | Current | Budget Remaining |")
    lines.append("|-----|--------|---------|------------------|")

    for slo in slos:
        name = slo.get("name", "unnamed")
        target = slo.get("target", "n/a")
        current = slo.get("current", "n/a")
        budget = slo.get("budget_remaining", "n/a")
        lines.append(f"| {name} | {target} | {current} | {budget} |")

    return "\n".join(lines)
