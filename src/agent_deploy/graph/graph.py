"""Build the deploy lifecycle StateGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from agent_deploy.graph.nodes.analyze import analyze_node, interpret_analysis_node
from agent_deploy.graph.nodes.approval_gate import approval_gate_node
from agent_deploy.graph.nodes.baseline import baseline_node
from agent_deploy.graph.nodes.changelog import changelog_node
from agent_deploy.graph.nodes.deploy_region import deploy_region_node
from agent_deploy.graph.nodes.monitor import monitor_node
from agent_deploy.graph.nodes.post_deploy import post_deploy_node, promote_node
from agent_deploy.graph.nodes.rc_selection import select_rc_node
from agent_deploy.graph.nodes.rollback import rollback_node
from agent_deploy.graph.nodes.routing import (
    route_after_analysis,
    route_after_approval,
    route_analysis,
    route_next_region,
)
from agent_deploy.graph.state import DeployState
from agent_deploy.llm.tools import o11y_tools


def build_deploy_graph() -> StateGraph:
    """Return an *uncompiled* StateGraph so the caller can attach a checkpointer."""

    builder = StateGraph(DeployState)

    # -- nodes --
    builder.add_node("select_rc", select_rc_node)
    builder.add_node("generate_changelog", changelog_node)
    builder.add_node("capture_baseline", baseline_node)
    builder.add_node("deploy_region", deploy_region_node)
    builder.add_node("monitor", monitor_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("o11y_tools", ToolNode(o11y_tools))
    builder.add_node("interpret", interpret_analysis_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("promote_region", promote_node)
    builder.add_node("rollback", rollback_node)
    builder.add_node("post_deploy", post_deploy_node)

    # -- linear flow --
    builder.add_edge(START, "select_rc")
    builder.add_edge("select_rc", "generate_changelog")
    builder.add_edge("generate_changelog", "capture_baseline")
    builder.add_edge("capture_baseline", "deploy_region")
    builder.add_edge("deploy_region", "monitor")
    builder.add_edge("monitor", "analyze")

    # -- ReAct analysis loop --
    builder.add_conditional_edges(
        "analyze",
        route_analysis,
        {"o11y_tools": "o11y_tools", "interpret": "interpret"},
    )
    builder.add_edge("o11y_tools", "analyze")

    # -- post-analysis routing --
    builder.add_conditional_edges(
        "interpret",
        route_after_analysis,
        {"approval_gate": "approval_gate", "rollback": "rollback"},
    )

    # -- approval -> next --
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {"promote_region": "promote_region", "rollback": "rollback"},
    )

    # -- region loop --
    builder.add_conditional_edges(
        "promote_region",
        route_next_region,
        {"deploy_region": "deploy_region", "post_deploy": "post_deploy"},
    )

    # -- terminal --
    builder.add_edge("post_deploy", END)
    builder.add_edge("rollback", END)

    return builder
