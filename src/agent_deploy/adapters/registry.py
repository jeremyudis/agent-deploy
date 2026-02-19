"""Adapter registry -- holds configured adapter instances and wires them from config."""

from __future__ import annotations

from typing import Any

import structlog

from agent_deploy.adapters.protocols import (
    DeployOrchestrator,
    GitAdapter,
    JobExecutor,
    Notifier,
    O11yAdapter,
)

log = structlog.get_logger()


class AdapterRegistry:
    """Holds a set of configured adapter instances used by the graph nodes."""

    def __init__(
        self,
        git: GitAdapter,
        deploy: DeployOrchestrator,
        o11y: O11yAdapter,
        notifier: Notifier,
        executor: JobExecutor,
    ) -> None:
        self.git = git
        self.deploy = deploy
        self.o11y = o11y
        self.notifier = notifier
        self.executor = executor

    async def close(self) -> None:
        """Close all adapters that have a close method."""
        for adapter in (self.git, self.deploy, self.o11y, self.notifier, self.executor):
            close = getattr(adapter, "close", None)
            if close:
                await close()

    @classmethod
    def from_config(cls, settings: Any) -> AdapterRegistry:
        """Build a registry from application settings.

        ``settings`` is expected to expose at minimum:
        - git_provider: str  ("github" | "gitlab")
        - deploy_provider: str  ("gitlab" | "jenkins")
        - o11y_provider: str  ("datadog" | "prometheus" | "splunk")
        - notify_provider: str  ("slack" | "cli")
        - executor_provider: str  ("gitlab" | "jenkins" | "k8s")
        Plus the relevant credentials / URLs for each chosen provider.
        """
        git = _build_git(settings)
        deploy = _build_deploy(settings)
        o11y = _build_o11y(settings)
        notifier = _build_notifier(settings)
        executor = _build_executor(settings)
        log.info(
            "adapter_registry_created",
            git=type(git).__name__,
            deploy=type(deploy).__name__,
            o11y=type(o11y).__name__,
            notifier=type(notifier).__name__,
            executor=type(executor).__name__,
        )
        return cls(git=git, deploy=deploy, o11y=o11y, notifier=notifier, executor=executor)


# ---------------------------------------------------------------------------
# Private builder helpers
# ---------------------------------------------------------------------------

def _build_git(settings: Any) -> GitAdapter:
    provider = getattr(settings, "git_provider", "github")
    if provider == "github":
        from agent_deploy.adapters.git.github import GitHubAdapter

        return GitHubAdapter(
            token=settings.github_token,
            owner=settings.github_owner,
            repo=settings.github_repo,
        )
    if provider == "gitlab":
        from agent_deploy.adapters.git.gitlab import GitLabGitAdapter

        return GitLabGitAdapter(
            token=settings.gitlab_token,
            project_id=settings.gitlab_project_id,
            base_url=getattr(settings, "gitlab_url", "https://gitlab.com/api/v4"),
        )
    raise ValueError(f"Unknown git provider: {provider}")


def _build_deploy(settings: Any) -> DeployOrchestrator:
    provider = getattr(settings, "deploy_provider", "gitlab")
    if provider == "gitlab":
        from agent_deploy.adapters.deploy.gitlab_ci import GitLabDeployOrchestrator

        return GitLabDeployOrchestrator(
            token=settings.gitlab_token,
            project_id=settings.gitlab_project_id,
            base_url=getattr(settings, "gitlab_url", "https://gitlab.com/api/v4"),
        )
    if provider == "jenkins":
        from agent_deploy.adapters.deploy.jenkins import JenkinsDeployOrchestrator

        return JenkinsDeployOrchestrator(
            base_url=settings.jenkins_url,
            user=settings.jenkins_user,
            api_token=settings.jenkins_api_token,
            job_name=getattr(settings, "jenkins_deploy_job", "deploy"),
        )
    raise ValueError(f"Unknown deploy provider: {provider}")


def _build_o11y(settings: Any) -> O11yAdapter:
    provider = getattr(settings, "o11y_provider", "datadog")
    if provider == "datadog":
        from agent_deploy.adapters.o11y.datadog import DatadogAdapter

        return DatadogAdapter(
            api_key=settings.datadog_api_key,
            app_key=settings.datadog_app_key,
            base_url=getattr(settings, "datadog_url", "https://api.datadoghq.com"),
        )
    if provider == "prometheus":
        from agent_deploy.adapters.o11y.prometheus import PrometheusAdapter

        return PrometheusAdapter(
            prometheus_url=settings.prometheus_url,
            alertmanager_url=getattr(settings, "alertmanager_url", None),
        )
    if provider == "splunk":
        from agent_deploy.adapters.o11y.splunk import SplunkAdapter

        return SplunkAdapter(
            base_url=settings.splunk_url,
            token=settings.splunk_token,
        )
    raise ValueError(f"Unknown o11y provider: {provider}")


def _build_notifier(settings: Any) -> Notifier:
    provider = getattr(settings, "notify_provider", "cli")
    if provider == "slack":
        from agent_deploy.adapters.notify.slack import SlackNotifier

        return SlackNotifier(
            bot_token=settings.slack_bot_token,
            app_token=getattr(settings, "slack_app_token", None),
        )
    if provider == "cli":
        from agent_deploy.adapters.notify.cli_notify import CLINotifier

        return CLINotifier()
    raise ValueError(f"Unknown notify provider: {provider}")


def _build_executor(settings: Any) -> JobExecutor:
    provider = getattr(settings, "executor_provider", "gitlab")
    if provider == "gitlab":
        from agent_deploy.adapters.executor.gitlab_executor import GitLabExecutor

        return GitLabExecutor(
            token=settings.gitlab_token,
            project_id=settings.gitlab_project_id,
            trigger_token=settings.gitlab_trigger_token,
            base_url=getattr(settings, "gitlab_url", "https://gitlab.com/api/v4"),
        )
    if provider == "jenkins":
        from agent_deploy.adapters.executor.jenkins_executor import JenkinsExecutor

        return JenkinsExecutor(
            base_url=settings.jenkins_url,
            user=settings.jenkins_user,
            api_token=settings.jenkins_api_token,
        )
    if provider == "k8s":
        from agent_deploy.adapters.executor.k8s_executor import K8sExecutor

        return K8sExecutor(
            namespace=getattr(settings, "k8s_namespace", "default"),
            kubeconfig=getattr(settings, "kubeconfig", None),
        )
    raise ValueError(f"Unknown executor provider: {provider}")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: AdapterRegistry | None = None


def get_registry() -> AdapterRegistry:
    """Return the current adapter registry; raises if not yet initialized."""
    if _registry is None:
        raise RuntimeError("AdapterRegistry has not been initialized. Call set_registry() first.")
    return _registry


def set_registry(registry: AdapterRegistry) -> None:
    """Set the module-level adapter registry singleton."""
    global _registry
    _registry = registry
