"""Splunk observability adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class SplunkAdapter:
    """Observability adapter backed by the Splunk REST API."""

    def __init__(self, base_url: str, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_alerts(self, service: str, region: str, since: datetime) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/services/alerts/fired_alerts",
            params={
                "output_mode": "json",
                "search": f"service={service} region={region}",
            },
        )
        resp.raise_for_status()
        return [
            {
                "name": a.get("name", ""),
                "severity": a.get("severity", ""),
                "triggered_at": a.get("trigger_time", ""),
            }
            for a in resp.json().get("entry", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_slo_status(self, service: str, region: str) -> list[dict[str, Any]]:
        search_query = (
            f'search index=slo service="{service}" region="{region}" '
            "| stats avg(sli) as sli_avg by slo_name"
        )
        return await self._run_search(search_query)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_metrics(
        self, service: str, region: str, metric_names: list[str], since: datetime
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name in metric_names:
            search_query = (
                f'search index=metrics metric_name="{name}" '
                f'service="{service}" region="{region}" '
                f'earliest="{since.strftime("%Y-%m-%dT%H:%M:%S")}" '
                "| timechart avg(value) as avg_value"
            )
            results[name] = await self._run_search(search_query)
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_logs(
        self, service: str, region: str, query: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        search_query = (
            f'search index=logs service="{service}" region="{region}" {query} '
            f"| head {limit}"
        )
        return await self._run_search(search_query)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_traces(
        self, service: str, region: str, sort_by: str = "duration", limit: int = 20
    ) -> list[dict[str, Any]]:
        search_query = (
            f'search index=traces service="{service}" region="{region}" '
            f"| sort -{sort_by} | head {limit}"
        )
        return await self._run_search(search_query)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def check_dependencies(self, service: str, direction: str = "downstream") -> dict[str, Any]:
        search_query = (
            f'search index=traces service="{service}" '
            "| stats count by peer_service | sort -count"
        )
        deps = await self._run_search(search_query)
        return {"service": service, "direction": direction, "dependencies": deps}

    async def _run_search(self, search_query: str) -> list[dict[str, Any]]:
        """Submit a search job and return results."""
        # Create the search job
        resp = await self._client.post(
            "/services/search/jobs",
            data={"search": search_query, "output_mode": "json", "exec_mode": "oneshot"},
        )
        resp.raise_for_status()
        data = resp.json()
        return [r for r in data.get("results", [])]
