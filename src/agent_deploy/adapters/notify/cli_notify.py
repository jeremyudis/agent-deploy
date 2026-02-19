"""CLI notifier adapter using rich console output."""

from __future__ import annotations

from typing import Any

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

log = structlog.get_logger()

_console = Console()


class CLINotifier:
    """Notifier that renders messages to the terminal via rich."""

    def __init__(self) -> None:
        self._console = _console

    async def close(self) -> None:
        pass

    async def send_approval_request(
        self,
        channel: str,
        service: str,
        version: str,
        region: str,
        deploy_id: str,
        summary: str,
    ) -> None:
        table = Table(title="Deploy Approval Request", show_header=False)
        table.add_row("Service", service)
        table.add_row("Version", version)
        table.add_row("Region", region)
        table.add_row("Deploy ID", deploy_id)
        table.add_row("Summary", summary)
        self._console.print(table)
        log.info("cli_approval_printed", service=service, deploy_id=deploy_id)

    async def send_notification(
        self,
        channel: str,
        message: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> None:
        self._console.print(Panel(message, title=f"Notification [{channel}]"))

    async def send_deploy_summary(
        self,
        channel: str,
        service: str,
        version: str,
        region: str,
        status: str,
        details: str,
    ) -> None:
        style = "green" if status == "success" else "red"
        self._console.print(
            Panel(
                f"[bold]{service}[/bold] {version} -> {region}\n"
                f"Status: [{style}]{status}[/{style}]\n\n{details}",
                title="Deploy Summary",
            )
        )
