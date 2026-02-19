"""RC selection node -- picks the latest tag as the release candidate."""

from __future__ import annotations

import structlog

from agent_deploy.adapters.registry import get_registry
from agent_deploy.graph.state import DeployState

log = structlog.get_logger()


async def select_rc_node(state: DeployState) -> dict:
    """Use the git adapter to fetch tags and select the latest as the RC version."""
    service = state.get("service", "unknown")
    log.info("select_rc_node.start", service=service)

    try:
        git = get_registry().git
        tags = await git.get_tags()

        if not tags:
            log.warning("select_rc_node.no_tags", service=service)
            return {"error_message": "No tags found in repository"}

        version = tags[0]  # tags are returned newest-first per protocol
        log.info("select_rc_node.selected", service=service, version=version)
        return {"version": version}

    except Exception as exc:
        log.error("select_rc_node.error", error=str(exc), service=service)
        return {"error_message": f"RC selection failed: {exc}"}
