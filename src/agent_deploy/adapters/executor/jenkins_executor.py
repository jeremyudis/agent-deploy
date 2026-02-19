"""Jenkins job executor."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class JenkinsExecutor:
    """Job executor that triggers Jenkins builds via the Remote Build API."""

    def __init__(self, base_url: str, user: str, api_token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(user, api_token),
            timeout=60.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def trigger_job(
        self,
        deploy_id: str,
        trigger: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> str:
        job_name = trigger.get("job_name", "deploy")
        build_params = {"DEPLOY_ID": deploy_id, **(params or {})}

        resp = await self._client.post(
            f"/job/{job_name}/buildWithParameters",
            params=build_params,
        )
        resp.raise_for_status()
        queue_url = resp.headers.get("Location", "")
        log.info("jenkins_job_triggered", queue_url=queue_url, deploy_id=deploy_id)
        return queue_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def schedule_cron(
        self,
        deploy_id: str,
        cron_expr: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        # Jenkins cron is configured via job XML; we update the job config
        job_name = f"agent-deploy-cron-{deploy_id}"
        config_xml = f"""<?xml version='1.0' encoding='UTF-8'?>
<project>
  <description>agent-deploy scheduled job for {deploy_id}</description>
  <triggers>
    <hudson.triggers.TimerTrigger>
      <spec>{cron_expr}</spec>
    </hudson.triggers.TimerTrigger>
  </triggers>
</project>"""
        resp = await self._client.post(
            f"/createItem?name={job_name}",
            content=config_xml,
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()
        log.info("jenkins_cron_scheduled", job_name=job_name, cron=cron_expr)
        return job_name

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def cancel_cron(self, schedule_id: str) -> None:
        resp = await self._client.post(f"/job/{schedule_id}/doDelete")
        resp.raise_for_status()
        log.info("jenkins_cron_cancelled", schedule_id=schedule_id)
