"""Prometheus observability adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class PrometheusAdapter:
    """Observability adapter backed by the Prometheus / Alertmanager HTTP APIs."""

    def __init__(
        self,
        prometheus_url: str,
        alertmanager_url: str | None = None,
    ) -> None:
        self._prom = httpx.AsyncClient(
            base_url=prometheus_url.rstrip("/"),
            timeout=30.0,
        )
        self._am: httpx.AsyncClient | None = None
        if alertmanager_url:
            self._am = httpx.AsyncClient(
                base_url=alertmanager_url.rstrip("/"),
                timeout=30.0,
            )

    async def close(self) -> None:
        await self._prom.aclose()
        if self._am:
            await self._am.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_alerts(self, service: str, region: str, since: datetime) -> list[dict[str, Any]]:
        if not self._am:
            log.warning("alertmanager_not_configured")
            return []
        resp = await self._am.get(
            "/api/v2/alerts",
            params={"filter": f'service="{service}",region="{region}"'},
        )
        resp.raise_for_status()
        return [
            {
                "name": a["labels"].get("alertname", ""),
                "status": a["status"]["state"],
                "starts_at": a.get("startsAt", ""),
                "summary": a["annotations"].get("summary", ""),
            }
            for a in resp.json()
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_slo_status(self, service: str, region: str) -> list[dict[str, Any]]:
        # Query SLO-related recording rules by convention
        query = f'slo:sli_error:ratio_rate30d{{service="{service}",region="{region}"}}'
        resp = await self._prom.get("/api/v1/query", params={"query": query})
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "metric": r["metric"],
                "value": r["value"][1] if len(r.get("value", [])) > 1 else None,
            }
            for r in data.get("data", {}).get("result", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_metrics(
        self, service: str, region: str, metric_names: list[str], since: datetime
    ) -> dict[str, Any]:
        now = datetime.now()
        results: dict[str, Any] = {}
        for name in metric_names:
            query = f'{name}{{service="{service}",region="{region}"}}'
            resp = await self._prom.get(
                "/api/v1/query_range",
                params={
                    "query": query,
                    "start": since.isoformat(),
                    "end": now.isoformat(),
                    "step": "60",
                },
            )
            resp.raise_for_status()
            results[name] = resp.json().get("data", {}).get("result", [])
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_logs(
        self, service: str, region: str, query: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        # Prometheus doesn't natively store logs; return empty
        log.warning("prometheus_get_logs_not_supported")
        return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_traces(
        self, service: str, region: str, sort_by: str = "duration", limit: int = 20
    ) -> list[dict[str, Any]]:
        # Prometheus doesn't natively store traces; return empty
        log.warning("prometheus_get_traces_not_supported")
        return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def check_dependencies(self, service: str, direction: str = "downstream") -> dict[str, Any]:
        # Use a PromQL query to approximate dependency relationships
        query = f'up{{service="{service}"}}'
        resp = await self._prom.get("/api/v1/query", params={"query": query})
        resp.raise_for_status()
        return {"service": service, "direction": direction, "data": resp.json().get("data", {})}
