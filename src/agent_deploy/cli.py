"""Typer CLI for agent-deploy."""

from __future__ import annotations

import json
import sys
import uuid

import structlog
import typer
from rich.console import Console
from rich.table import Table

from agent_deploy.config import AgentDeploySettings
from agent_deploy.db import DeployRun, get_engine, get_session
from agent_deploy.graph.graph import build_deploy_graph

log = structlog.get_logger()
console = Console()
app = typer.Typer(name="agent-deploy")


def _compile_graph(settings: AgentDeploySettings):
    """Build and compile the deploy graph with a Postgres checkpointer."""
    from langgraph.checkpoint.postgres import PostgresSaver

    checkpointer = PostgresSaver.from_conn_string(settings.database_url)
    builder = build_deploy_graph()
    return builder.compile(checkpointer=checkpointer)


def _init_registry(settings: AgentDeploySettings):
    """Create an AdapterRegistry from settings and install it as the singleton."""
    from agent_deploy.adapters.registry import AdapterRegistry, set_registry

    registry = AdapterRegistry.from_config(settings)
    set_registry(registry)
    return registry


@app.command()
def start(
    service: str = typer.Option(..., help="Service name"),
    version: str = typer.Option(..., help="Version / tag to deploy"),
    regions: str = typer.Option(..., help="Comma-separated target regions"),
) -> None:
    """Start a new progressive deploy."""
    settings = AgentDeploySettings()
    deploy_id = f"deploy-{uuid.uuid4().hex[:12]}"

    region_list = [r.strip() for r in regions.split(",") if r.strip()]

    # Persist the run
    engine = get_engine(settings.database_url)
    session = get_session(engine)
    run = DeployRun(
        deploy_id=deploy_id,
        service=service,
        version=version,
        regions=region_list,
        status="started",
    )
    session.add(run)
    session.commit()
    session.close()

    console.print(f"[bold green]Deploy created:[/bold green] {deploy_id}")
    console.print(f"  service={service}  version={version}  regions={region_list}")

    # Initialize adapters and invoke graph
    _init_registry(settings)
    graph = _compile_graph(settings)

    initial_state = {
        "messages": [],
        "deploy_id": deploy_id,
        "service": service,
        "version": version,
        "target_regions": region_list,
        "current_region": region_list[0],
        "current_region_index": 0,
        "regions_completed": [],
        "changelog_summary": "",
        "high_risk_changes": [],
        "baseline_snapshot": {},
        "monitoring_snapshots": [],
        "alerts_fired": [],
        "analysis_decision": "",
        "analysis_confidence": 0.0,
        "analysis_reasoning": "",
        "analysis_evidence": [],
        "approval_status": "",
        "approver": "",
        "rollback_needed": False,
        "error_message": "",
        "bake_window_elapsed": False,
    }

    config = {"configurable": {"thread_id": deploy_id}}
    graph.invoke(initial_state, config)
    console.print(f"[bold]Deploy {deploy_id} graph invoked.[/bold]")


@app.command()
def status(
    deploy_id: str = typer.Option(..., help="Deploy ID to query"),
) -> None:
    """Show the status of a deploy run."""
    settings = AgentDeploySettings()
    engine = get_engine(settings.database_url)
    session = get_session(engine)

    run = session.query(DeployRun).filter_by(deploy_id=deploy_id).first()
    session.close()

    if not run:
        console.print(f"[red]Deploy {deploy_id} not found.[/red]")
        raise typer.Exit(code=1)

    table = Table(title=f"Deploy {deploy_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Service", run.service)
    table.add_row("Version", run.version)
    table.add_row("Regions", json.dumps(run.regions))
    table.add_row("Status", run.status)
    table.add_row("Created", str(run.created_at))
    table.add_row("Updated", str(run.updated_at))
    console.print(table)


@app.command()
def approve(
    deploy_id: str = typer.Option(..., help="Deploy ID"),
    region: str = typer.Option(..., help="Region to approve"),
) -> None:
    """Approve a deploy that is waiting for human review."""
    settings = AgentDeploySettings()
    _init_registry(settings)
    graph = _compile_graph(settings)

    config = {"configurable": {"thread_id": deploy_id}}
    from langgraph.types import Command

    graph.invoke(
        Command(resume={"approved": True, "approver": "cli-user"}),
        config,
    )
    console.print(f"[green]Approved deploy {deploy_id} for region {region}.[/green]")


@app.command()
def reject(
    deploy_id: str = typer.Option(..., help="Deploy ID"),
    region: str = typer.Option(..., help="Region to reject"),
    reason: str = typer.Option("", help="Rejection reason"),
) -> None:
    """Reject a deploy that is waiting for human review."""
    settings = AgentDeploySettings()
    _init_registry(settings)
    graph = _compile_graph(settings)

    config = {"configurable": {"thread_id": deploy_id}}
    from langgraph.types import Command

    graph.invoke(
        Command(resume={"approved": False, "approver": "cli-user", "reason": reason}),
        config,
    )
    console.print(f"[yellow]Rejected deploy {deploy_id} for region {region}.[/yellow]")


@app.command()
def rollback(
    deploy_id: str = typer.Option(..., help="Deploy ID to rollback"),
) -> None:
    """Force a rollback for a deploy."""
    settings = AgentDeploySettings()
    _init_registry(settings)
    graph = _compile_graph(settings)

    config = {"configurable": {"thread_id": deploy_id}}
    from langgraph.types import Command

    graph.invoke(
        Command(resume={"approved": False, "approver": "cli-user", "reason": "forced rollback"}),
        config,
    )
    console.print(f"[red]Rollback initiated for deploy {deploy_id}.[/red]")


@app.command()
def run(
    deploy_id: str = typer.Option(..., help="Deploy ID"),
    trigger: str = typer.Option("start", help="Trigger type: start | resume | cron"),
    resume_data: str = typer.Option("", help="JSON-encoded resume payload"),
) -> None:
    """CI entry point: load checkpoint, invoke graph, handle lifecycle.

    This is the command executed by CI jobs (GitLab CI / Jenkins) to drive
    the deploy graph forward.
    """
    settings = AgentDeploySettings()
    _init_registry(settings)
    graph = _compile_graph(settings)

    config = {"configurable": {"thread_id": deploy_id}}

    if trigger == "start":
        initial_state = {
            "messages": [],
            "deploy_id": deploy_id,
            "service": "",
            "version": "",
            "target_regions": [],
            "current_region": "",
            "current_region_index": 0,
            "regions_completed": [],
            "changelog_summary": "",
            "high_risk_changes": [],
            "baseline_snapshot": {},
            "monitoring_snapshots": [],
            "alerts_fired": [],
            "analysis_decision": "",
            "analysis_confidence": 0.0,
            "analysis_reasoning": "",
            "analysis_evidence": [],
            "approval_status": "",
            "approver": "",
            "rollback_needed": False,
            "error_message": "",
            "bake_window_elapsed": False,
        }
        graph.invoke(initial_state, config)
    elif trigger == "resume":
        from langgraph.types import Command

        data = json.loads(resume_data) if resume_data else {}
        graph.invoke(Command(resume=data), config)
    else:
        # Cron / crash recovery — continue from last checkpoint
        graph.invoke(None, config)

    # Check post-run state
    state = graph.get_state(config)
    pending = getattr(state, "tasks", None)

    if pending:
        log.info("run.waiting_for_human", deploy_id=deploy_id)
        sys.exit(0)

    log.info("run.completed", deploy_id=deploy_id)
    sys.exit(0)
