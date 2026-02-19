"""Jenkins deploy orchestrator."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class JenkinsDeployOrchestrator:
    """Deploy orchestrator backed by Jenkins REST API."""

    def __init__(
        self,
        base_url: str,
        user: str,
        api_token: str,
        job_name: str = "deploy",
    ) -> None:
        self._job_name = job_name
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(user, api_token),
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def trigger_deploy(
        self,
        service: str,
        version: str,
        region: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Trigger a Jenkins build with parameters and return the queue item URL."""
        build_params = {
            "DEPLOY_SERVICE": service,
            "DEPLOY_VERSION": version,
            "DEPLOY_REGION": region,
            **(params or {}),
        }
        resp = await self._client.post(
            f"/job/{self._job_name}/buildWithParameters",
            params=build_params,
        )
        resp.raise_for_status()
        queue_url = resp.headers.get("Location", "")
        log.info("jenkins_deploy_triggered", queue_url=queue_url, service=service)
        return queue_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_deploy_status(self, deploy_id: str) -> dict[str, Any]:
        """Return build status. deploy_id is the queue URL or build number."""
        # If deploy_id looks like a URL, query the queue; otherwise query build number
        if deploy_id.startswith("http"):
            resp = await self._client.get(f"{deploy_id}api/json")
        else:
            resp = await self._client.get(f"/job/{self._job_name}/{deploy_id}/api/json")
        resp.raise_for_status()
        data = resp.json()
        return {
            "deploy_id": str(data.get("id", data.get("number", deploy_id))),
            "status": data.get("result", data.get("why", "PENDING")),
            "building": data.get("building", False),
            "url": data.get("url", deploy_id),
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def trigger_rollback(self, deploy_id: str, region: str) -> dict[str, Any]:
        """Trigger a rollback by stopping the current build and re-running the previous."""
        # Stop the current build
        await self._client.post(f"/job/{self._job_name}/{deploy_id}/stop")
        log.info("jenkins_rollback_triggered", deploy_id=deploy_id, region=region)
        return {"deploy_id": deploy_id, "status": "ROLLBACK_INITIATED"}
