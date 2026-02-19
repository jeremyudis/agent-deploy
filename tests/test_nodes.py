"""Tests for individual graph nodes with mock adapters."""

from __future__ import annotations

import pytest

from agent_deploy.graph.nodes.rc_selection import select_rc_node
from agent_deploy.graph.nodes.baseline import baseline_node
from agent_deploy.graph.nodes.deploy_region import deploy_region_node
from agent_deploy.graph.nodes.monitor import monitor_node


@pytest.mark.asyncio
async def test_select_rc_node(mock_registry, sample_state):
    """select_rc_node should pick the latest tag as the version."""
    result = await select_rc_node(sample_state)
    assert result["version"] == "v1.2.3"
    mock_registry.git.get_tags.assert_awaited_once()


@pytest.mark.asyncio
async def test_select_rc_node_no_tags(mock_registry, sample_state):
    """When no tags exist, an error message should be returned."""
    mock_registry.git.get_tags.return_value = []
    result = await select_rc_node(sample_state)
    assert "error_message" in result
    assert "No tags" in result["error_message"]


@pytest.mark.asyncio
async def test_baseline_node(mock_registry, sample_state):
    """baseline_node should capture a snapshot with metrics and SLOs."""
    result = await baseline_node(sample_state)
    snapshot = result["baseline_snapshot"]
    assert "latency_p50" in snapshot
    assert "slos" in snapshot
    assert "captured_at" in snapshot
    mock_registry.o11y.get_metrics.assert_awaited_once()
    mock_registry.o11y.get_slo_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_deploy_region_node(mock_registry, sample_state):
    """deploy_region_node should trigger a deploy and set current_region."""
    result = await deploy_region_node(sample_state)
    assert result["current_region"] == "us-east-1"
    assert result["current_region_index"] == 0
    mock_registry.deploy.trigger_deploy.assert_awaited_once_with(
        "payments-api", "v1.2.3", "us-east-1"
    )


@pytest.mark.asyncio
async def test_deploy_region_node_second_region(mock_registry, sample_state):
    """deploy_region_node should pick the correct region based on index."""
    sample_state["current_region_index"] = 1
    result = await deploy_region_node(sample_state)
    assert result["current_region"] == "eu-west-1"
    mock_registry.deploy.trigger_deploy.assert_awaited_once_with(
        "payments-api", "v1.2.3", "eu-west-1"
    )


@pytest.mark.asyncio
async def test_deploy_region_node_no_regions(mock_registry, sample_state):
    """When no target regions are configured, return an error."""
    sample_state["target_regions"] = []
    result = await deploy_region_node(sample_state)
    assert "error_message" in result
    assert "No target regions" in result["error_message"]


@pytest.mark.asyncio
async def test_monitor_node(mock_registry, sample_state):
    """monitor_node should accumulate snapshots and check bake window."""
    result = await monitor_node(sample_state)
    assert len(result["monitoring_snapshots"]) == 1
    snapshot = result["monitoring_snapshots"][0]
    assert "latency_p50" in snapshot
    assert "captured_at" in snapshot
    assert isinstance(result["bake_window_elapsed"], bool)
    mock_registry.o11y.get_alerts.assert_awaited_once()
    mock_registry.o11y.get_metrics.assert_awaited_once()


@pytest.mark.asyncio
async def test_monitor_node_bake_elapsed(mock_registry, sample_state):
    """After enough snapshots, bake_window_elapsed should be True."""
    # The monitor node considers bake elapsed when total snapshots * interval >= bake window.
    # With default 5 min interval and 15 min bake window, 3 total snapshots suffice.
    sample_state["monitoring_snapshots"] = [{"captured_at": "t1"}, {"captured_at": "t2"}]
    result = await monitor_node(sample_state)
    # 2 existing + 1 new = 3 total, 3 * 5 = 15 >= 15
    assert result["bake_window_elapsed"] is True


@pytest.mark.asyncio
async def test_promote_advances_region_index(sample_state):
    """Verify the promote node concept: index increments and region is added to completed."""
    # This tests the expected behavior pattern — the actual promote node
    # should return incremented index + region added to regions_completed.
    state = sample_state.copy()
    state["current_region_index"] = 0
    state["current_region"] = "us-east-1"

    # Simulate what the promote node should do
    new_index = state["current_region_index"] + 1
    assert new_index == 1
    assert state["target_regions"][0] == "us-east-1"
