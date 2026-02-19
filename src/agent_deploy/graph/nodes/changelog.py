"""Changelog node -- generates a changelog summary using git data and an LLM."""

from __future__ import annotations

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from agent_deploy.adapters.registry import get_registry
from agent_deploy.graph.state import DeployState
from agent_deploy.llm.context import build_changelog_context
from agent_deploy.llm.prompts import CHANGELOG_SYSTEM_PROMPT

log = structlog.get_logger()


async def changelog_node(state: DeployState) -> dict:
    """Generate a changelog summary by analyzing git diff and commits with an LLM."""
    service = state.get("service", "unknown")
    version = state.get("version", "unknown")
    log.info("changelog_node.start", service=service, version=version)

    try:
        git = get_registry().git
        tags = await git.get_tags()

        # Determine the previous version (second tag) for the diff range
        if len(tags) >= 2:
            from_ref = tags[1]
        else:
            from_ref = "HEAD~10"  # fallback: compare against recent history

        to_ref = version

        diff = await git.get_diff(from_ref, to_ref)
        commits = await git.get_commits(from_ref, to_ref)

        log.info(
            "changelog_node.fetched",
            service=service,
            from_ref=from_ref,
            to_ref=to_ref,
            commit_count=len(commits),
        )

    except Exception as exc:
        log.error("changelog_node.git_error", error=str(exc), service=service)
        return {"error_message": f"Changelog git fetch failed: {exc}"}

    try:
        context = build_changelog_context(diff, commits)
        llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=2048)

        response = await llm.ainvoke([
            SystemMessage(content=CHANGELOG_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ])

        changelog_text = response.content
        if isinstance(changelog_text, list):
            changelog_text = "\n".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in changelog_text
            )

        # Extract high-risk changes (lines prefixed with [HIGH RISK])
        high_risk = [
            line.strip().removeprefix("- ").strip()
            for line in changelog_text.splitlines()
            if "[HIGH RISK]" in line
        ]

        log.info(
            "changelog_node.done",
            service=service,
            high_risk_count=len(high_risk),
        )
        return {
            "changelog_summary": changelog_text,
            "high_risk_changes": high_risk,
        }

    except Exception as exc:
        log.error("changelog_node.llm_error", error=str(exc), service=service)
        return {"error_message": f"Changelog LLM analysis failed: {exc}"}
