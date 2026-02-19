"""Slack notifier adapter using slack-bolt."""

from __future__ import annotations

from typing import Any

import structlog
from slack_bolt.async_app import AsyncApp
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class SlackNotifier:
    """Notifier backed by the Slack API via slack-bolt."""

    def __init__(self, bot_token: str, app_token: str | None = None) -> None:
        self._app = AsyncApp(token=bot_token)
        self._client = self._app.client

    async def close(self) -> None:
        # slack-bolt manages its own session; nothing to close
        pass

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_approval_request(
        self,
        channel: str,
        service: str,
        version: str,
        region: str,
        deploy_id: str,
        summary: str,
    ) -> None:
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Deploy Approval: {service} {version}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Service:* {service}\n*Version:* {version}\n"
                        f"*Region:* {region}\n*Deploy ID:* {deploy_id}\n\n{summary}"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "action_id": "deploy_approve",
                        "value": deploy_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "action_id": "deploy_reject",
                        "value": deploy_id,
                    },
                ],
            },
        ]
        await self._client.chat_postMessage(channel=channel, text=f"Deploy approval: {service} {version}", blocks=blocks)
        log.info("slack_approval_sent", channel=channel, service=service, deploy_id=deploy_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_notification(
        self,
        channel: str,
        message: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> None:
        await self._client.chat_postMessage(channel=channel, text=message, blocks=blocks)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def send_deploy_summary(
        self,
        channel: str,
        service: str,
        version: str,
        region: str,
        status: str,
        details: str,
    ) -> None:
        color = "#36a64f" if status == "success" else "#ff0000"
        attachments = [
            {
                "color": color,
                "title": f"Deploy Summary: {service} {version} -> {region}",
                "text": details,
                "fields": [
                    {"title": "Status", "value": status, "short": True},
                    {"title": "Region", "value": region, "short": True},
                ],
            }
        ]
        await self._client.chat_postMessage(
            channel=channel,
            text=f"Deploy {status}: {service} {version}",
            attachments=attachments,
        )
        log.info("slack_deploy_summary_sent", channel=channel, service=service, status=status)
