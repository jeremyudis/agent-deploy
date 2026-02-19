"""Approval gate node -- sends notification and waits for human approval."""

from __future__ import annotations

import structlog
from langgraph.types import interrupt

from agent_deploy.adapters.registry import get_registry
from agent_deploy.graph.state import DeployState

log = structlog.get_logger()


async def approval_gate_node(state: DeployState) -> dict:
    """Send an approval request and interrupt the graph to wait for a human decision."""
    service = state.get("service", "unknown")
    version = state.get("version", "unknown")
    region = state.get("current_region", "unknown")
    deploy_id = state.get("deploy_id", "unknown")
    decision = state.get("analysis_decision", "unknown")
    confidence = state.get("analysis_confidence", 0.0)
    reasoning = state.get("analysis_reasoning", "")

    log.info(
        "approval_gate_node.start",
        service=service,
        version=version,
        region=region,
        decision=decision,
        confidence=confidence,
    )

    summary = (
        f"Analysis decision: {decision} (confidence: {confidence:.0%})\n"
        f"Reasoning: {reasoning}"
    )

    try:
        notifier = get_registry().notifier
        await notifier.send_approval_request(
            channel=f"#deploy-{service}",
            service=service,
            version=version,
            region=region,
            deploy_id=deploy_id,
            summary=summary,
        )
    except Exception as exc:
        log.error("approval_gate_node.notify_error", error=str(exc))

    # Interrupt the graph execution and wait for human input
    approval = interrupt(
        {
            "type": "approval_request",
            "service": service,
            "version": version,
            "region": region,
            "deploy_id": deploy_id,
            "analysis_decision": decision,
            "analysis_confidence": confidence,
            "analysis_reasoning": reasoning,
        }
    )

    approved = approval.get("approved", False) if isinstance(approval, dict) else False
    approver = approval.get("approver", "unknown") if isinstance(approval, dict) else "unknown"

    log.info(
        "approval_gate_node.resolved",
        approved=approved,
        approver=approver,
        service=service,
        region=region,
    )

    return {
        "approval_status": "approved" if approved else "rejected",
        "approver": approver,
        "rollback_needed": not approved,
    }
