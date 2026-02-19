"""Monitor node -- polls observability signals during the bake window."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog

from agent_deploy.adapters.registry import get_registry
from agent_deploy.graph.state import DeployState

log = structlog.get_logger()

_DEFAULT_METRICS = [
    "latency_p50",
    "latency_p99",
    "error_rate",
    "request_rate",
    "cpu_utilization",
    "memory_utilization",
]

# Defaults if not configured via state
_DEFAULT_BAKE_MINUTES = 15
_DEFAULT_POLL_INTERVAL_MINUTES = 5


async def monitor_node(state: DeployState) -> dict:
    """Poll alerts and metrics, determine if the bake window has elapsed."""
    service = state.get("service", "unknown")
    region = state.get("current_region", "unknown")
    existing_snapshots = state.get("monitoring_snapshots", [])
    log.info(
        "monitor_node.start",
        service=service,
        region=region,
        snapshot_count=len(existing_snapshots),
    )

    try:
        o11y = get_registry().o11y
        since = datetime.now(timezone.utc) - timedelta(minutes=_DEFAULT_POLL_INTERVAL_MINUTES)

        alerts = await o11y.get_alerts(service, region, since)
        metrics = await o11y.get_metrics(service, region, _DEFAULT_METRICS, since)

        snapshot = {
            **metrics,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        # Determine if bake window has elapsed
        total_snapshots = len(existing_snapshots) + 1
        elapsed_minutes = total_snapshots * _DEFAULT_POLL_INTERVAL_MINUTES
        bake_elapsed = elapsed_minutes >= _DEFAULT_BAKE_MINUTES

        log.info(
            "monitor_node.polled",
            service=service,
            region=region,
            alerts_count=len(alerts),
            elapsed_minutes=elapsed_minutes,
            bake_elapsed=bake_elapsed,
        )

        return {
            "monitoring_snapshots": [snapshot],
            "alerts_fired": alerts,
            "bake_window_elapsed": bake_elapsed,
        }

    except Exception as exc:
        log.error("monitor_node.error", error=str(exc), service=service, region=region)
        return {"error_message": f"Monitoring poll failed: {exc}"}
