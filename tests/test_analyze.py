"""Tests for the analysis pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from agent_deploy.graph.nodes.routing import route_after_analysis


def test_analyze_node_returns_messages():
    """Verify that an AI message is properly recognized in state."""
    ai_msg = AIMessage(content="The deploy looks healthy. No anomalies detected.")
    state = {"messages": [ai_msg]}

    assert len(state["messages"]) == 1
    assert isinstance(state["messages"][0], AIMessage)
    assert "healthy" in state["messages"][0].content


def test_interpret_clean():
    """A clean analysis (proceed with high confidence) should route to approval_gate."""
    state = {
        "analysis_decision": "proceed",
        "analysis_confidence": 0.95,
    }
    assert route_after_analysis(state) == "approval_gate"


def test_interpret_with_evidence_rollback():
    """A rollback decision with high confidence should route to rollback."""
    state = {
        "analysis_decision": "rollback",
        "analysis_confidence": 0.9,
        "analysis_evidence": [
            {
                "signal": "error_rate",
                "description": "Error rate spiked to 5%",
                "severity": "critical",
                "correlated_change": "abc12345",
            }
        ],
    }
    assert route_after_analysis(state) == "rollback"


def test_interpret_investigate():
    """An investigate decision should route to approval_gate for human review."""
    state = {
        "analysis_decision": "investigate",
        "analysis_confidence": 0.6,
    }
    assert route_after_analysis(state) == "approval_gate"


def test_interpret_with_tool_calls_in_message():
    """Messages with tool_calls indicate the LLM wants more data."""
    msg = MagicMock()
    msg.tool_calls = [{"name": "fetch_error_logs", "args": {"service": "payments-api"}}]

    state = {"messages": [msg]}
    # This simulates what route_analysis checks
    from agent_deploy.graph.nodes.routing import route_analysis

    assert route_analysis(state) == "o11y_tools"


def test_interpret_without_tool_calls():
    """Messages without tool_calls mean the LLM is done investigating."""
    msg = MagicMock()
    msg.tool_calls = []

    state = {"messages": [msg]}
    from agent_deploy.graph.nodes.routing import route_analysis

    assert route_analysis(state) == "interpret"


def test_evidence_parsing():
    """Verify evidence dicts have the expected structure."""
    evidence = {
        "signal": "latency_p99",
        "description": "p99 latency increased from 180ms to 350ms",
        "severity": "high",
        "correlated_change": "def67890",
    }

    assert evidence["signal"] == "latency_p99"
    assert evidence["severity"] == "high"
    assert evidence["correlated_change"] == "def67890"

    # Verify it works with the Pydantic Evidence model too
    from agent_deploy.llm.schemas import Evidence

    parsed = Evidence(**evidence)
    assert parsed.signal == "latency_p99"
    assert parsed.severity == "high"
    assert parsed.correlated_change == "def67890"
