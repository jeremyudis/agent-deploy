"""GitLab CI deploy orchestrator."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class GitLabDeployOrchestrator:
    """Deploy orchestrator backed by GitLab CI pipelines."""

    def __init__(self, token: str, project_id: str, base_url: str = "https://gitlab.com/api/v4") -> None:
        self._project_id = project_id
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"PRIVATE-TOKEN": token},
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _proj(self) -> str:
        return quote(self._project_id, safe="")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def trigger_deploy(
        self,
        service: str,
        version: str,
        region: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Trigger a deploy pipeline and return pipeline ID."""
        variables = [
            {"key": "DEPLOY_SERVICE", "value": service},
            {"key": "DEPLOY_VERSION", "value": version},
            {"key": "DEPLOY_REGION", "value": region},
        ]
        for k, v in (params or {}).items():
            variables.append({"key": k, "value": str(v)})

        resp = await self._client.post(
            f"/projects/{self._proj()}/pipeline",
            json={"ref": version, "variables": variables},
        )
        resp.raise_for_status()
        pipeline_id = str(resp.json()["id"])
        log.info("gitlab_deploy_triggered", pipeline_id=pipeline_id, service=service, version=version)
        return pipeline_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_deploy_status(self, deploy_id: str) -> dict[str, Any]:
        """Return current status of a pipeline."""
        resp = await self._client.get(
            f"/projects/{self._proj()}/pipelines/{deploy_id}",
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "deploy_id": str(data["id"]),
            "status": data["status"],
            "web_url": data.get("web_url", ""),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def trigger_rollback(self, deploy_id: str, region: str) -> dict[str, Any]:
        """Retry (rollback) a pipeline by creating a new one from the same ref."""
        resp = await self._client.post(
            f"/projects/{self._proj()}/pipelines/{deploy_id}/retry",
        )
        resp.raise_for_status()
        data = resp.json()
        log.info("gitlab_rollback_triggered", pipeline_id=data["id"], region=region)
        return {
            "deploy_id": str(data["id"]),
            "status": data["status"],
        }
