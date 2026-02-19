"""Rollback node -- triggers a rollback and sends notification."""

from __future__ import annotations

import structlog

from agent_deploy.adapters.registry import get_registry
from agent_deploy.graph.state import DeployState

log = structlog.get_logger()


async def rollback_node(state: DeployState) -> dict:
    """Trigger a rollback for the current deploy and notify the team."""
    service = state.get("service", "unknown")
    version = state.get("version", "unknown")
    region = state.get("current_region", "unknown")
    deploy_id = state.get("deploy_id", "unknown")
    reasoning = state.get("analysis_reasoning", "No reasoning provided")

    log.info(
        "rollback_node.start",
        service=service,
        version=version,
        region=region,
        deploy_id=deploy_id,
    )

    try:
        deploy = get_registry().deploy
        result = await deploy.trigger_rollback(deploy_id, region)
        log.info(
            "rollback_node.triggered",
            service=service,
            region=region,
            result=result,
        )
    except Exception as exc:
        log.error("rollback_node.rollback_error", error=str(exc), deploy_id=deploy_id)

    try:
        notifier = get_registry().notifier
        await notifier.send_deploy_summary(
            channel=f"#deploy-{service}",
            service=service,
            version=version,
            region=region,
            status="rolled_back",
            details=f"Rollback triggered. Reason: {reasoning}",
        )
    except Exception as exc:
        log.error("rollback_node.notify_error", error=str(exc))

    return {"rollback_needed": True}
