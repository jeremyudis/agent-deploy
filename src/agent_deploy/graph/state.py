"""Deploy graph state schema."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class DeployState(TypedDict):
    """Full state carried through the deploy graph."""

    # Conversation / tool-call messages
    messages: Annotated[list[AnyMessage], add_messages]

    # Deploy identity
    deploy_id: str
    service: str
    version: str

    # Region rollout
    target_regions: list[str]
    current_region: str
    current_region_index: int
    regions_completed: Annotated[list[str], operator.add]

    # Changelog analysis
    changelog_summary: str
    high_risk_changes: list[str]

    # Observability
    baseline_snapshot: dict
    monitoring_snapshots: Annotated[list[dict], operator.add]
    alerts_fired: Annotated[list[dict], operator.add]

    # LLM analysis verdict
    analysis_decision: str
    analysis_confidence: float
    analysis_reasoning: str
    analysis_evidence: list[dict]

    # Approval
    approval_status: str
    approver: str

    # Control flow
    rollback_needed: bool
    error_message: str
    bake_window_elapsed: bool
