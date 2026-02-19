"""Tests for graph construction and routing logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from agent_deploy.graph.graph import build_deploy_graph
from agent_deploy.graph.nodes.routing import (
    route_after_analysis,
    route_after_approval,
    route_analysis,
    route_next_region,
)


def test_graph_compiles():
    """build_deploy_graph() should compile without error."""
    builder = build_deploy_graph()
    graph = builder.compile()
    assert graph is not None


# ---- route_analysis -------------------------------------------------------

def test_route_analysis_with_tool_calls():
    """When the last message has tool_calls, route to 'o11y_tools'."""
    msg = MagicMock()
    msg.tool_calls = [{"name": "fetch_detailed_metrics", "args": {}}]
    state = {"messages": [msg]}
    assert route_analysis(state) == "o11y_tools"


def test_route_analysis_without_tool_calls():
    """When the last message has no tool_calls, route to 'interpret'."""
    msg = MagicMock()
    msg.tool_calls = []
    state = {"messages": [msg]}
    assert route_analysis(state) == "interpret"


def test_route_analysis_empty_messages():
    """When there are no messages at all, route to 'interpret'."""
    state = {"messages": []}
    assert route_analysis(state) == "interpret"


# ---- route_after_analysis --------------------------------------------------

def test_route_after_analysis_rollback():
    """High-confidence rollback should route to 'rollback'."""
    state = {"analysis_decision": "rollback", "analysis_confidence": 0.95}
    assert route_after_analysis(state) == "rollback"


def test_route_after_analysis_proceed():
    """Non-rollback decision should route to 'approval_gate'."""
    state = {"analysis_decision": "proceed", "analysis_confidence": 0.9}
    assert route_after_analysis(state) == "approval_gate"


def test_route_after_analysis_low_confidence_rollback():
    """Low-confidence rollback should still go to approval_gate."""
    state = {"analysis_decision": "rollback", "analysis_confidence": 0.5}
    assert route_after_analysis(state) == "approval_gate"


# ---- route_after_approval --------------------------------------------------

def test_route_after_approval_approved():
    """Approved status should route to 'promote_region'."""
    state = {"approval_status": "approved"}
    assert route_after_approval(state) == "promote_region"


def test_route_after_approval_rejected():
    """Non-approved status should route to 'rollback'."""
    state = {"approval_status": "rejected"}
    assert route_after_approval(state) == "rollback"


# ---- route_next_region -----------------------------------------------------

def test_route_next_region_more_regions():
    """When there are more regions, route to 'deploy_region'."""
    state = {
        "current_region_index": 0,
        "target_regions": ["us-east-1", "eu-west-1", "ap-southeast-1"],
    }
    assert route_next_region(state) == "deploy_region"


def test_route_next_region_done():
    """When all regions are done, route to 'post_deploy'."""
    state = {
        "current_region_index": 2,
        "target_regions": ["us-east-1", "eu-west-1", "ap-southeast-1"],
    }
    assert route_next_region(state) == "post_deploy"


def test_route_next_region_single_region():
    """A single-region deploy should go to 'post_deploy' after first promote."""
    state = {
        "current_region_index": 0,
        "target_regions": ["us-east-1"],
    }
    assert route_next_region(state) == "post_deploy"
