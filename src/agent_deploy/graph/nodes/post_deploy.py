"""Post-deploy nodes -- summary, region promotion, and next-region check."""

from __future__ import annotations

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agent_deploy.adapters.registry import get_registry
from agent_deploy.graph.state import DeployState
from agent_deploy.llm.prompts import POST_DEPLOY_SUMMARY_PROMPT

log = structlog.get_logger()


async def post_deploy_node(state: DeployState) -> dict:
    """Generate a final deploy summary using an LLM and notify the team."""
    service = state.get("service", "unknown")
    version = state.get("version", "unknown")
    regions_completed = state.get("regions_completed", [])
    rollback_needed = state.get("rollback_needed", False)

    log.info(
        "post_deploy_node.start",
        service=service,
        version=version,
        regions_completed=regions_completed,
    )

    # Build context for the summary LLM
    context_parts = [
        f"Service: {service}",
        f"Version: {version}",
        f"Regions completed: {', '.join(regions_completed) if regions_completed else 'none'}",
        f"Rollback triggered: {rollback_needed}",
        f"Changelog: {state.get('changelog_summary', 'N/A')}",
        f"Analysis decision: {state.get('analysis_decision', 'N/A')}",
        f"Analysis reasoning: {state.get('analysis_reasoning', 'N/A')}",
    ]

    alerts = state.get("alerts_fired", [])
    if alerts:
        context_parts.append(f"Alerts fired: {len(alerts)}")

    context = "\n".join(context_parts)

    try:
        llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=1024)
        response = await llm.ainvoke([
            SystemMessage(content=POST_DEPLOY_SUMMARY_PROMPT),
            HumanMessage(content=context),
        ])

        summary = response.content
        if isinstance(summary, list):
            summary = "\n".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in summary
            )

        log.info("post_deploy_node.summary_generated", service=service)

    except Exception as exc:
        log.error("post_deploy_node.llm_error", error=str(exc))
        summary = f"Deploy of {service} {version} completed. Regions: {', '.join(regions_completed)}."

    # Send notification
    try:
        notifier = get_registry().notifier
        status = "rolled_back" if rollback_needed else "success"
        await notifier.send_deploy_summary(
            channel=f"#deploy-{service}",
            service=service,
            version=version,
            region="all",
            status=status,
            details=summary,
        )
    except Exception as exc:
        log.error("post_deploy_node.notify_error", error=str(exc))

    return {}


async def promote_node(state: DeployState) -> dict:
    """Add the current region to regions_completed and advance the index."""
    region = state.get("current_region", "unknown")
    index = state.get("current_region_index", 0)

    log.info("promote_node.promoting", region=region, index=index)

    return {
        "regions_completed": [region],
        "current_region_index": index + 1,
    }


async def check_next_region_node(state: DeployState) -> dict:
    """Pass-through node -- routing is handled by the conditional edge."""
    return {}
