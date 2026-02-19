"""Datadog observability adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class DatadogAdapter:
    """Observability adapter backed by the Datadog API."""

    def __init__(self, api_key: str, app_key: str, base_url: str = "https://api.datadoghq.com") -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "DD-API-KEY": api_key,
                "DD-APPLICATION-KEY": app_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_alerts(self, service: str, region: str, since: datetime) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/api/v1/monitor",
            params={
                "monitor_tags": f"service:{service},region:{region}",
            },
        )
        resp.raise_for_status()
        since_ts = since.timestamp()
        return [
            {
                "id": m["id"],
                "name": m["name"],
                "status": m["overall_state"],
                "message": m.get("message", ""),
            }
            for m in resp.json()
            if m.get("overall_state") != "OK"
            or (m.get("modified") and datetime.fromisoformat(m["modified"]).timestamp() >= since_ts)
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_slo_status(self, service: str, region: str) -> list[dict[str, Any]]:
        resp = await self._client.get(
            "/api/v1/slo",
            params={"tags": f"service:{service},region:{region}"},
        )
        resp.raise_for_status()
        return [
            {
                "id": s["id"],
                "name": s["name"],
                "target": s.get("target_threshold"),
                "status": s.get("overall_status", []),
            }
            for s in resp.json().get("data", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_metrics(
        self, service: str, region: str, metric_names: list[str], since: datetime
    ) -> dict[str, Any]:
        now = int(datetime.now().timestamp())
        start = int(since.timestamp())
        results: dict[str, Any] = {}
        for name in metric_names:
            query = f"avg:{name}{{service:{service},region:{region}}}"
            resp = await self._client.get(
                "/api/v1/query",
                params={"from": start, "to": now, "query": query},
            )
            resp.raise_for_status()
            results[name] = resp.json().get("series", [])
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_logs(
        self, service: str, region: str, query: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        resp = await self._client.post(
            "/api/v2/logs/events/search",
            json={
                "filter": {
                    "query": f"service:{service} region:{region} {query}",
                },
                "page": {"limit": limit},
            },
        )
        resp.raise_for_status()
        return [
            {
                "timestamp": e["attributes"].get("timestamp"),
                "message": e["attributes"].get("message", ""),
                "status": e["attributes"].get("status", ""),
            }
            for e in resp.json().get("data", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_traces(
        self, service: str, region: str, sort_by: str = "duration", limit: int = 20
    ) -> list[dict[str, Any]]:
        resp = await self._client.post(
            "/api/v2/spans/events/search",
            json={
                "filter": {
                    "query": f"service:{service} region:{region}",
                },
                "sort": f"-{sort_by}",
                "page": {"limit": limit},
            },
        )
        resp.raise_for_status()
        return [
            {
                "trace_id": s["attributes"].get("trace_id"),
                "span_id": s["attributes"].get("span_id"),
                "duration": s["attributes"].get("duration"),
                "resource": s["attributes"].get("resource_name", ""),
            }
            for s in resp.json().get("data", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def check_dependencies(self, service: str, direction: str = "downstream") -> dict[str, Any]:
        resp = await self._client.get(
            "/api/v1/service_dependencies",
            params={"service": service, "direction": direction},
        )
        resp.raise_for_status()
        return resp.json()
