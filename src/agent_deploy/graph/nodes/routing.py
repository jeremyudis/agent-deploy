"""Conditional edge functions for the deploy graph."""

from agent_deploy.graph.state import DeployState


def route_analysis(state: DeployState) -> str:
    """Route after the analyse node calls the LLM.

    If the last message contains tool_calls the LLM wants to invoke
    observability tools; otherwise it is ready to interpret results.
    """
    messages = state["messages"]
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        return "o11y_tools"
    return "interpret"


def route_after_analysis(state: DeployState) -> str:
    """Route based on the LLM analysis verdict.

    High-confidence rollback decisions go straight to rollback;
    everything else proceeds to the approval gate.
    """
    if state.get("analysis_decision") == "rollback" and state.get("analysis_confidence", 0) > 0.8:
        return "rollback"
    return "approval_gate"


def route_after_approval(state: DeployState) -> str:
    """Route based on approval status."""
    if state.get("approval_status") == "approved":
        return "promote_region"
    return "rollback"


def route_next_region(state: DeployState) -> str:
    """Route after a region is promoted.

    If there are more regions to deploy, loop back; otherwise finish up.
    """
    index = state.get("current_region_index", 0)
    regions = state.get("target_regions", [])
    if index + 1 < len(regions):
        return "deploy_region"
    return "post_deploy"
