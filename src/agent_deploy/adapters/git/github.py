"""GitHub adapter for Git operations."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class GitHubAdapter:
    """Git adapter backed by the GitHub REST API."""

    def __init__(self, token: str, owner: str, repo: str, base_url: str = "https://api.github.com") -> None:
        self._owner = owner
        self._repo = repo
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_diff(self, from_ref: str, to_ref: str) -> str:
        """Return the unified diff between two refs."""
        resp = await self._client.get(
            f"/repos/{self._owner}/{self._repo}/compare/{from_ref}...{to_ref}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        resp.raise_for_status()
        return resp.text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_commits(self, from_ref: str, to_ref: str) -> list[dict[str, Any]]:
        """Return commit metadata between two refs."""
        resp = await self._client.get(
            f"/repos/{self._owner}/{self._repo}/compare/{from_ref}...{to_ref}",
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "sha": c["sha"],
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            }
            for c in data.get("commits", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_tags(self) -> list[str]:
        """Return tag names, newest first."""
        resp = await self._client.get(
            f"/repos/{self._owner}/{self._repo}/tags",
            params={"per_page": 100},
        )
        resp.raise_for_status()
        return [t["name"] for t in resp.json()]
