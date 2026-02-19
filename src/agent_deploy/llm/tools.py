"""LangGraph tool definitions for observability investigation.

Each tool wraps an adapter method so the LLM can pull additional
signals during deploy-health analysis.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from agent_deploy.adapters.registry import get_registry


def _run_async(coro):
    """Run an async coroutine from a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


@tool
def fetch_detailed_metrics(
    service: str,
    metric_name: str,
    region: str,
    minutes: int = 30,
) -> dict:
    """Fetch detailed time-series metrics for a service.

    Use this tool when golden-signal summaries show an anomaly and you
    need finer-grained data to confirm or rule out a regression.

    Args:
        service: The service name (e.g. "payments-api").
        metric_name: The metric to retrieve (e.g. "request_latency_p99",
            "error_rate", "cpu_utilization", "memory_usage").
        region: The deployment region (e.g. "us-east-1").
        minutes: How far back to look. Defaults to 30.

    Returns:
        A dict with metric data including timestamps and values.
    """
    try:
        o11y = get_registry().o11y
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return _run_async(
            o11y.get_metrics(service, region, [metric_name], since)
        )
    except Exception as exc:
        return {"error": str(exc), "tool": "fetch_detailed_metrics"}


@tool
def fetch_error_logs(
    service: str,
    region: str,
    query: str = "level:ERROR",
    limit: int = 50,
) -> dict:
    """Fetch recent error logs for a service.

    Use this tool when error-rate metrics spike and you need to
    understand *which* errors are occurring and whether they correlate
    with a specific changelog entry.

    Args:
        service: The service name.
        region: The deployment region.
        query: A log query string. Defaults to "level:ERROR".
        limit: Maximum number of log entries to return. Defaults to 50.

    Returns:
        A list of log entry dicts matching the query.
    """
    try:
        o11y = get_registry().o11y
        result = _run_async(
            o11y.get_logs(service, region, query, limit)
        )
        return {"entries": result}
    except Exception as exc:
        return {"error": str(exc), "tool": "fetch_error_logs"}


@tool
def fetch_trace_exemplars(
    service: str,
    region: str,
    sort_by: str = "duration",
    limit: int = 5,
) -> dict:
    """Fetch distributed-trace exemplars for a service.

    Use this tool when latency metrics are degraded and you want to
    inspect individual slow requests to find the bottleneck span.

    Args:
        service: The service name.
        region: The deployment region.
        sort_by: Sort criterion -- "duration" (slowest first) or
            "timestamp" (most recent first). Defaults to "duration".
        limit: Number of traces to return. Defaults to 5.

    Returns:
        A dict with traces containing trace_id, duration_ms, and spans.
    """
    try:
        o11y = get_registry().o11y
        result = _run_async(
            o11y.get_traces(service, region, sort_by, limit)
        )
        return {"traces": result}
    except Exception as exc:
        return {"error": str(exc), "tool": "fetch_trace_exemplars"}


@tool
def check_dependent_services(
    service: str,
    direction: str = "both",
) -> dict:
    """Check the health of services that depend on or are depended upon.

    Use this tool when you suspect a deploy may have impacted upstream
    callers or downstream dependencies.

    Args:
        service: The service name.
        direction: Which direction to check -- "upstream", "downstream",
            or "both". Defaults to "both".

    Returns:
        A dict with dependency health information.
    """
    try:
        o11y = get_registry().o11y
        return _run_async(
            o11y.check_dependencies(service, direction)
        )
    except Exception as exc:
        return {"error": str(exc), "tool": "check_dependent_services"}


o11y_tools = [
    fetch_detailed_metrics,
    fetch_error_logs,
    fetch_trace_exemplars,
    check_dependent_services,
]
