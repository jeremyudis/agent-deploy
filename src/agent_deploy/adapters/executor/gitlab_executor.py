"""GitLab pipeline executor."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class GitLabExecutor:
    """Job executor that triggers GitLab CI pipelines via the Pipeline Trigger API."""

    def __init__(
        self,
        token: str,
        project_id: str,
        trigger_token: str,
        base_url: str = "https://gitlab.com/api/v4",
    ) -> None:
        self._project_id = project_id
        self._trigger_token = trigger_token
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
    async def trigger_job(
        self,
        deploy_id: str,
        trigger: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> str:
        ref = trigger.get("ref", "main")
        variables = {"DEPLOY_ID": deploy_id}
        variables.update(params or {})

        resp = await self._client.post(
            f"/projects/{self._proj()}/trigger/pipeline",
            data={
                "token": self._trigger_token,
                "ref": ref,
                **{f"variables[{k}]": str(v) for k, v in variables.items()},
            },
        )
        resp.raise_for_status()
        pipeline_id = str(resp.json()["id"])
        log.info("gitlab_job_triggered", pipeline_id=pipeline_id, deploy_id=deploy_id)
        return pipeline_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def schedule_cron(
        self,
        deploy_id: str,
        cron_expr: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        variables = [{"key": "DEPLOY_ID", "value": deploy_id}]
        for k, v in (params or {}).items():
            variables.append({"key": k, "value": str(v)})

        resp = await self._client.post(
            f"/projects/{self._proj()}/pipeline_schedules",
            json={
                "description": f"agent-deploy cron for {deploy_id}",
                "ref": "main",
                "cron": cron_expr,
                "cron_timezone": "UTC",
            },
        )
        resp.raise_for_status()
        schedule_id = str(resp.json()["id"])

        # Add variables to the schedule
        for var in variables:
            await self._client.post(
                f"/projects/{self._proj()}/pipeline_schedules/{schedule_id}/variables",
                json=var,
            )

        log.info("gitlab_cron_scheduled", schedule_id=schedule_id, cron=cron_expr)
        return schedule_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def cancel_cron(self, schedule_id: str) -> None:
        resp = await self._client.delete(
            f"/projects/{self._proj()}/pipeline_schedules/{schedule_id}",
        )
        resp.raise_for_status()
        log.info("gitlab_cron_cancelled", schedule_id=schedule_id)
