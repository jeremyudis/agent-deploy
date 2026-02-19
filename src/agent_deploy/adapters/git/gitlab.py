"""GitLab adapter for Git operations."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class GitLabGitAdapter:
    """Git adapter backed by the GitLab REST API."""

    def __init__(self, token: str, project_id: str, base_url: str = "https://gitlab.com/api/v4") -> None:
        self._project_id = project_id
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"PRIVATE-TOKEN": token},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_diff(self, from_ref: str, to_ref: str) -> str:
        """Return the unified diff between two refs."""
        resp = await self._client.get(
            f"/projects/{quote(self._project_id, safe='')}/repository/compare",
            params={"from": from_ref, "to": to_ref},
        )
        resp.raise_for_status()
        data = resp.json()
        # Reconstruct unified diff from GitLab's diff array
        parts: list[str] = []
        for d in data.get("diffs", []):
            parts.append(f"--- a/{d['old_path']}\n+++ b/{d['new_path']}\n{d['diff']}")
        return "\n".join(parts)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_commits(self, from_ref: str, to_ref: str) -> list[dict[str, Any]]:
        """Return commit metadata between two refs."""
        resp = await self._client.get(
            f"/projects/{quote(self._project_id, safe='')}/repository/compare",
            params={"from": from_ref, "to": to_ref},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "sha": c["id"],
                "message": c["message"],
                "author": c["author_name"],
                "date": c["created_at"],
            }
            for c in data.get("commits", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_tags(self) -> list[str]:
        """Return tag names, newest first."""
        resp = await self._client.get(
            f"/projects/{quote(self._project_id, safe='')}/repository/tags",
            params={"per_page": 100, "order_by": "updated", "sort": "desc"},
        )
        resp.raise_for_status()
        return [t["name"] for t in resp.json()]
