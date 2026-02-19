"""Baseline node -- captures pre-deploy observability snapshot."""

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


async def baseline_node(state: DeployState) -> dict:
    """Capture pre-deploy metrics and SLO status as a baseline snapshot."""
    service = state.get("service", "unknown")
    region = state.get("current_region", "unknown")
    log.info("baseline_node.start", service=service, region=region)

    try:
        o11y = get_registry().o11y
        since = datetime.now(timezone.utc) - timedelta(minutes=30)

        metrics = await o11y.get_metrics(service, region, _DEFAULT_METRICS, since)
        slos = await o11y.get_slo_status(service, region)

        snapshot = {
            **metrics,
            "slos": slos,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        log.info("baseline_node.captured", service=service, region=region)
        return {"baseline_snapshot": snapshot}

    except Exception as exc:
        log.error("baseline_node.error", error=str(exc), service=service, region=region)
        return {"error_message": f"Baseline capture failed: {exc}"}
