"""FastAPI webhook server for Slack interactions and deploy callbacks."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import structlog
from fastapi import FastAPI, Header, Request, Response

from agent_deploy.adapters.registry import get_registry
from agent_deploy.config import AgentDeploySettings

log = structlog.get_logger()
app = FastAPI(title="agent-deploy-webhook")

_settings: AgentDeploySettings | None = None


def _get_settings() -> AgentDeploySettings:
    global _settings
    if _settings is None:
        _settings = AgentDeploySettings()
    return _settings


def _verify_slack_signature(
    body: bytes, timestamp: str, signature: str, signing_secret: str
) -> bool:
    """Verify the Slack request signature."""
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/slack/actions")
async def slack_actions(
    request: Request,
    x_slack_request_timestamp: str = Header(""),
    x_slack_signature: str = Header(""),
) -> Response:
    """Handle Slack interactive message payloads (approve/reject buttons)."""
    settings = _get_settings()
    body = await request.body()

    if settings.slack_signing_secret and not _verify_slack_signature(
        body, x_slack_request_timestamp, x_slack_signature, settings.slack_signing_secret
    ):
        log.warning("slack_actions.invalid_signature")
        return Response(status_code=401, content="invalid signature")

    form = await request.form()
    payload = json.loads(form.get("payload", "{}"))
    actions = payload.get("actions", [])
    user = payload.get("user", {}).get("name", "unknown")

    for action in actions:
        action_id = action.get("action_id", "")
        value = json.loads(action.get("value", "{}"))
        deploy_id = value.get("deploy_id", "")
        region = value.get("region", "")

        if not deploy_id:
            continue

        if action_id == "approve_deploy":
            resume_data = {"approved": True, "approver": user}
        elif action_id == "reject_deploy":
            resume_data = {"approved": False, "approver": user, "reason": f"Rejected by {user}"}
        else:
            continue

        log.info(
            "slack_actions.triggering_resume",
            deploy_id=deploy_id,
            action=action_id,
            user=user,
        )

        executor = get_registry().executor
        await executor.trigger_job(
            deploy_id=deploy_id,
            trigger={"type": "resume"},
            params={"resume_data": json.dumps(resume_data)},
        )

    return Response(status_code=200, content="ok")


@app.post("/webhook/deploy-callback/{deploy_id}")
async def deploy_callback(deploy_id: str, request: Request) -> dict:
    """Handle deploy orchestrator completion callbacks.

    The orchestrator (GitLab CI, Jenkins, etc.) calls this endpoint when a
    deploy pipeline finishes so the graph can continue.
    """
    body = await request.json()
    status = body.get("status", "unknown")

    log.info(
        "deploy_callback.received",
        deploy_id=deploy_id,
        status=status,
    )

    executor = get_registry().executor
    await executor.trigger_job(
        deploy_id=deploy_id,
        trigger={"type": "callback", "status": status},
        params=body,
    )

    return {"received": True, "deploy_id": deploy_id}
