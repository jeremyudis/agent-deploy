"""Shared test fixtures for agent-deploy."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agent_deploy.adapters.registry import AdapterRegistry, set_registry


@pytest.fixture()
def mock_git_adapter():
    """A mock GitAdapter that returns fake diffs, commits, and tags."""
    adapter = AsyncMock()
    adapter.get_diff = AsyncMock(
        return_value="--- a/service.py\n+++ b/service.py\n@@ -1 +1 @@\n-old\n+new"
    )
    adapter.get_commits = AsyncMock(
        return_value=[
            {"sha": "abc12345", "message": "fix: handle timeout in payments"},
            {"sha": "def67890", "message": "feat: add retry logic to checkout"},
        ]
    )
    adapter.get_tags = AsyncMock(return_value=["v1.2.3", "v1.2.2", "v1.2.1"])
    return adapter


@pytest.fixture()
def mock_deploy_orchestrator():
    """A mock DeployOrchestrator that returns fake deploy IDs and statuses."""
    adapter = AsyncMock()
    adapter.trigger_deploy = AsyncMock(return_value="deploy-abc123")
    adapter.get_deploy_status = AsyncMock(return_value={"status": "success", "region": "us-east-1"})
    adapter.trigger_rollback = AsyncMock(return_value={"status": "rolled_back", "region": "us-east-1"})
    return adapter


@pytest.fixture()
def mock_o11y_adapter():
    """A mock O11yAdapter that returns fake alerts, metrics, and SLOs."""
    adapter = AsyncMock()
    adapter.get_alerts = AsyncMock(
        return_value=[
            {"name": "HighErrorRate", "severity": "critical", "message": "Error rate > 5%"},
        ]
    )
    adapter.get_slo_status = AsyncMock(
        return_value=[
            {"name": "availability", "target": "99.9%", "current": "99.85%", "budget_remaining": "15%"},
        ]
    )
    adapter.get_metrics = AsyncMock(
        return_value={
            "latency_p50": 45.0,
            "latency_p99": 200.0,
            "error_rate": 0.5,
            "request_rate": 1200.0,
            "cpu_utilization": 65.0,
            "memory_utilization": 72.0,
        }
    )
    adapter.get_logs = AsyncMock(return_value=[])
    adapter.get_traces = AsyncMock(return_value=[])
    adapter.check_dependencies = AsyncMock(return_value={})
    return adapter


@pytest.fixture()
def mock_notifier():
    """A mock Notifier that captures sent messages."""
    adapter = AsyncMock()
    adapter.sent_messages: list[dict[str, Any]] = []

    async def _capture_notification(channel: str, message: str, blocks=None):
        adapter.sent_messages.append({"channel": channel, "message": message, "blocks": blocks})

    adapter.send_notification = AsyncMock(side_effect=_capture_notification)
    adapter.send_approval_request = AsyncMock()
    adapter.send_deploy_summary = AsyncMock()
    return adapter


@pytest.fixture()
def mock_executor():
    """A mock JobExecutor that captures triggered jobs."""
    adapter = AsyncMock()
    adapter.triggered_jobs: list[dict[str, Any]] = []

    async def _capture_trigger(deploy_id: str, trigger: dict, params=None):
        adapter.triggered_jobs.append(
            {"deploy_id": deploy_id, "trigger": trigger, "params": params}
        )
        return "job-xyz"

    adapter.trigger_job = AsyncMock(side_effect=_capture_trigger)
    adapter.schedule_cron = AsyncMock(return_value="cron-123")
    adapter.cancel_cron = AsyncMock()
    return adapter


@pytest.fixture()
def mock_registry(
    mock_git_adapter,
    mock_deploy_orchestrator,
    mock_o11y_adapter,
    mock_notifier,
    mock_executor,
):
    """Set up a full AdapterRegistry with all mocks and install it as the singleton."""
    registry = AdapterRegistry(
        git=mock_git_adapter,
        deploy=mock_deploy_orchestrator,
        o11y=mock_o11y_adapter,
        notifier=mock_notifier,
        executor=mock_executor,
    )
    set_registry(registry)
    return registry


@pytest.fixture()
def sample_state() -> dict:
    """A valid DeployState dict with all fields populated."""
    return {
        "messages": [],
        "deploy_id": "deploy-test123",
        "service": "payments-api",
        "version": "v1.2.3",
        "target_regions": ["us-east-1", "eu-west-1", "ap-southeast-1"],
        "current_region": "us-east-1",
        "current_region_index": 0,
        "regions_completed": [],
        "changelog_summary": "fix: handle timeout in payments\nfeat: add retry logic",
        "high_risk_changes": ["Database migration: add index on orders.created_at"],
        "baseline_snapshot": {
            "latency_p50": 42.0,
            "latency_p99": 180.0,
            "error_rate": 0.1,
            "request_rate": 1000.0,
            "cpu_utilization": 60.0,
            "memory_utilization": 70.0,
            "slos": [
                {
                    "name": "availability",
                    "target": "99.9%",
                    "current": "99.95%",
                    "budget_remaining": "50%",
                }
            ],
            "captured_at": datetime.now(timezone.utc).isoformat(),
        },
        "monitoring_snapshots": [
            {
                "latency_p50": 45.0,
                "latency_p99": 200.0,
                "error_rate": 0.5,
                "request_rate": 1200.0,
                "cpu_utilization": 65.0,
                "memory_utilization": 72.0,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "alerts_fired": [
            {"name": "HighErrorRate", "severity": "critical", "message": "Error rate > 5%"},
        ],
        "analysis_decision": "proceed",
        "analysis_confidence": 0.9,
        "analysis_reasoning": "All signals are within normal thresholds.",
        "analysis_evidence": [],
        "approval_status": "",
        "approver": "",
        "rollback_needed": False,
        "error_message": "",
        "bake_window_elapsed": False,
    }
