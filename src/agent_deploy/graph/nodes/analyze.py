"""Analyze nodes -- LLM-driven deploy health analysis (ReAct loop)."""

from __future__ import annotations

import json

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agent_deploy.graph.state import DeployState
from agent_deploy.llm.context import build_analysis_context
from agent_deploy.llm.prompts import ANALYSIS_SYSTEM_PROMPT
from agent_deploy.llm.schemas import AnalysisResult, Decision
from agent_deploy.llm.tools import o11y_tools

log = structlog.get_logger()


async def analyze_node(state: DeployState) -> dict:
    """Core LLM analysis node with tool-calling capability (ReAct pattern).

    Builds context from state, invokes the LLM with o11y tools bound.
    Returns the AI message (which may contain tool_calls for the routing
    function to dispatch to the o11y_tools ToolNode).
    """
    service = state.get("service", "unknown")
    region = state.get("current_region", "unknown")
    messages = state.get("messages", [])

    log.info("analyze_node.start", service=service, region=region)

    llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=4096)
    llm_with_tools = llm.bind_tools(o11y_tools)

    # On the first call (no existing messages), build the full context
    if not messages:
        context = build_analysis_context(state)
        invoke_messages = [
            SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ]
    else:
        # Subsequent calls: the messages list already contains the conversation
        # including tool results. Prepend the system prompt.
        invoke_messages = [
            SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
            *messages,
        ]

    try:
        ai_message = await llm_with_tools.ainvoke(invoke_messages)
        log.info(
            "analyze_node.invoked",
            service=service,
            region=region,
            has_tool_calls=bool(ai_message.tool_calls),
        )
        return {"messages": [ai_message]}

    except Exception as exc:
        log.error("analyze_node.error", error=str(exc), service=service, region=region)
        return {"error_message": f"LLM analysis failed: {exc}"}


async def interpret_analysis_node(state: DeployState) -> dict:
    """Parse the last AI message into a structured AnalysisResult."""
    service = state.get("service", "unknown")
    region = state.get("current_region", "unknown")
    messages = state.get("messages", [])

    log.info("interpret_analysis_node.start", service=service, region=region)

    if not messages:
        log.warning("interpret_analysis_node.no_messages")
        return {
            "analysis_decision": Decision.INVESTIGATE.value,
            "analysis_confidence": 0.0,
            "analysis_reasoning": "No analysis messages available",
            "analysis_evidence": [],
        }

    last_message = messages[-1]
    content = last_message.content
    if isinstance(content, list):
        content = "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )

    # Try to parse structured output from the LLM response
    try:
        result = _extract_analysis_result(content)
        log.info(
            "interpret_analysis_node.parsed",
            service=service,
            region=region,
            decision=result.decision.value,
            confidence=result.confidence,
        )
        return {
            "analysis_decision": result.decision.value,
            "analysis_confidence": result.confidence,
            "analysis_reasoning": result.reasoning,
            "analysis_evidence": [e.model_dump() for e in result.evidence],
        }

    except Exception as exc:
        log.warning(
            "interpret_analysis_node.parse_fallback",
            error=str(exc),
            service=service,
        )
        # Fallback: use heuristics on the raw text
        return _fallback_interpretation(content)


def _extract_analysis_result(content: str) -> AnalysisResult:
    """Attempt to extract a structured AnalysisResult from LLM output."""
    # Look for JSON block in the response
    for marker_start, marker_end in [("```json", "```"), ("```", "```")]:
        if marker_start in content:
            start = content.index(marker_start) + len(marker_start)
            end = content.index(marker_end, start)
            json_str = content[start:end].strip()
            data = json.loads(json_str)
            return AnalysisResult.model_validate(data)

    # Try parsing the entire content as JSON
    data = json.loads(content)
    return AnalysisResult.model_validate(data)


def _fallback_interpretation(content: str) -> dict:
    """Heuristic fallback when structured parsing fails."""
    content_lower = content.lower()

    if "rollback" in content_lower:
        decision = Decision.ROLLBACK.value
        confidence = 0.6
    elif "proceed" in content_lower and "healthy" in content_lower:
        decision = Decision.PROCEED.value
        confidence = 0.6
    else:
        decision = Decision.INVESTIGATE.value
        confidence = 0.3

    return {
        "analysis_decision": decision,
        "analysis_confidence": confidence,
        "analysis_reasoning": content[:500],
        "analysis_evidence": [],
    }
