"""Deploy region node -- triggers a deployment for the current region."""

from __future__ import annotations

import structlog

from agent_deploy.adapters.registry import get_registry
from agent_deploy.graph.state import DeployState

log = structlog.get_logger()


async def deploy_region_node(state: DeployState) -> dict:
    """Trigger a deploy for the next target region."""
    service = state.get("service", "unknown")
    version = state.get("version", "unknown")
    target_regions = state.get("target_regions", [])
    index = state.get("current_region_index", 0)

    if not target_regions:
        log.error("deploy_region_node.no_regions", service=service)
        return {"error_message": "No target regions configured"}

    region = target_regions[index]
    log.info(
        "deploy_region_node.start",
        service=service,
        version=version,
        region=region,
        index=index,
    )

    try:
        deploy = get_registry().deploy
        deploy_id = await deploy.trigger_deploy(service, version, region)

        log.info(
            "deploy_region_node.triggered",
            service=service,
            version=version,
            region=region,
            deploy_id=deploy_id,
        )
        return {
            "current_region": region,
            "current_region_index": index,
        }

    except Exception as exc:
        log.error(
            "deploy_region_node.error",
            error=str(exc),
            service=service,
            region=region,
        )
        return {"error_message": f"Deploy trigger failed for {region}: {exc}"}
