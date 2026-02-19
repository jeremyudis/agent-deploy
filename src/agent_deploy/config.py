"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentDeploySettings(BaseSettings):
    """Central configuration for agent-deploy.

    All fields can be overridden via environment variables prefixed with
    ``AGENT_DEPLOY_`` (e.g. ``AGENT_DEPLOY_DATABASE_URL``).
    """

    model_config = SettingsConfigDict(env_prefix="AGENT_DEPLOY_")

    # Core
    database_url: str = "postgresql://localhost:5432/agent_deploy"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5-20250929"

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_channel: str = "#deploys"

    # Provider selection
    git_provider: str = "github"
    deploy_provider: str = "gitlab"
    o11y_provider: str = "datadog"
    notify_provider: str = "slack"
    executor_provider: str = "gitlab"

    # GitHub
    github_token: str = ""
    github_owner: str = ""
    github_repo: str = ""

    # GitLab
    gitlab_url: str = "https://gitlab.com/api/v4"
    gitlab_token: str = ""
    gitlab_project_id: str = ""
    gitlab_trigger_token: str = ""

    # Jenkins
    jenkins_url: str = ""
    jenkins_user: str = ""
    jenkins_api_token: str = ""
    jenkins_deploy_job: str = "deploy"

    # Datadog
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    datadog_url: str = "https://api.datadoghq.com"

    # Prometheus
    prometheus_url: str = ""
    alertmanager_url: str = ""

    # Splunk
    splunk_url: str = ""
    splunk_token: str = ""

    # K8s
    k8s_namespace: str = "default"
    kubeconfig: str | None = None

    # Deploy behavior
    bake_window_minutes: int = 30
    monitor_interval_minutes: int = 5
    approval_timeout_minutes: int = 120
    approval_timeout_action: str = "escalate"
    max_analysis_tool_rounds: int = 3
