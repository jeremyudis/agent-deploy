"""Protocol definitions for all adapter interfaces."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GitAdapter(Protocol):
    """Adapter for interacting with a Git hosting platform (GitHub, GitLab, etc.)."""

    async def get_diff(self, from_ref: str, to_ref: str) -> str:
        """Return the unified diff between two refs."""
        ...

    async def get_commits(self, from_ref: str, to_ref: str) -> list[dict[str, Any]]:
        """Return commit metadata between two refs."""
        ...

    async def get_tags(self) -> list[str]:
        """Return a list of tag names, newest first."""
        ...


@runtime_checkable
class DeployOrchestrator(Protocol):
    """Adapter for triggering and managing deployments."""

    async def trigger_deploy(
        self,
        service: str,
        version: str,
        region: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Trigger a deploy and return the deploy ID."""
        ...

    async def get_deploy_status(self, deploy_id: str) -> dict[str, Any]:
        """Return current status of a deploy."""
        ...

    async def trigger_rollback(self, deploy_id: str, region: str) -> dict[str, Any]:
        """Trigger a rollback for the given deploy and return status."""
        ...


@runtime_checkable
class O11yAdapter(Protocol):
    """Adapter for observability data (metrics, alerts, logs, traces, SLOs)."""

    async def get_alerts(
        self, service: str, region: str, since: datetime
    ) -> list[dict[str, Any]]:
        """Return active or recent alerts for a service in a region."""
        ...

    async def get_slo_status(
        self, service: str, region: str
    ) -> list[dict[str, Any]]:
        """Return current SLO burn-rate / compliance for a service."""
        ...

    async def get_metrics(
        self,
        service: str,
        region: str,
        metric_names: list[str],
        since: datetime,
    ) -> dict[str, Any]:
        """Return time-series metric data."""
        ...

    async def get_logs(
        self,
        service: str,
        region: str,
        query: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return log entries matching a query."""
        ...

    async def get_traces(
        self,
        service: str,
        region: str,
        sort_by: str = "duration",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return sampled traces for a service."""
        ...

    async def check_dependencies(
        self, service: str, direction: str = "downstream"
    ) -> dict[str, Any]:
        """Return a dependency map for the service."""
        ...


@runtime_checkable
class Notifier(Protocol):
    """Adapter for sending human-facing notifications."""

    async def send_approval_request(
        self,
        channel: str,
        service: str,
        version: str,
        region: str,
        deploy_id: str,
        summary: str,
    ) -> None:
        """Send an approval-request message (e.g. Slack interactive message)."""
        ...

    async def send_notification(
        self,
        channel: str,
        message: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> None:
        """Send a plain notification message."""
        ...

    async def send_deploy_summary(
        self,
        channel: str,
        service: str,
        version: str,
        region: str,
        status: str,
        details: str,
    ) -> None:
        """Send a deploy-summary message."""
        ...


@runtime_checkable
class JobExecutor(Protocol):
    """Adapter for triggering CI/CD jobs or pipelines."""

    async def trigger_job(
        self,
        deploy_id: str,
        trigger: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> str:
        """Trigger a job/pipeline and return its job ID."""
        ...

    async def schedule_cron(
        self,
        deploy_id: str,
        cron_expr: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Schedule a recurring job and return its schedule ID."""
        ...

    async def cancel_cron(self, schedule_id: str) -> None:
        """Cancel a previously-scheduled cron job."""
        ...
