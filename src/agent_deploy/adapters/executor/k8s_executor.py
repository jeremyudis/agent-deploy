"""Kubernetes job executor."""

from __future__ import annotations

from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()

try:
    from kubernetes import client as k8s_client
    from kubernetes import config as k8s_config

    _HAS_K8S = True
except ImportError:
    _HAS_K8S = False


class K8sExecutor:
    """Job executor that creates Kubernetes Jobs / CronJobs."""

    def __init__(self, namespace: str = "default", kubeconfig: str | None = None) -> None:
        if not _HAS_K8S:
            raise RuntimeError(
                "kubernetes package is not installed. "
                "Install it with: pip install 'agent-deploy[k8s]'"
            )
        if kubeconfig:
            k8s_config.load_kube_config(config_file=kubeconfig)
        else:
            try:
                k8s_config.load_incluster_config()
            except k8s_config.ConfigException:
                k8s_config.load_kube_config()

        self._namespace = namespace
        self._batch = k8s_client.BatchV1Api()

    async def close(self) -> None:
        # kubernetes client manages its own connections
        pass

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def trigger_job(
        self,
        deploy_id: str,
        trigger: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> str:
        image = trigger.get("image", "busybox")
        command = trigger.get("command", ["/bin/sh", "-c", "echo deploy"])
        job_name = f"deploy-{deploy_id}"

        env_vars = [
            k8s_client.V1EnvVar(name="DEPLOY_ID", value=deploy_id),
        ]
        for k, v in (params or {}).items():
            env_vars.append(k8s_client.V1EnvVar(name=k, value=str(v)))

        job = k8s_client.V1Job(
            metadata=k8s_client.V1ObjectMeta(name=job_name, namespace=self._namespace),
            spec=k8s_client.V1JobSpec(
                template=k8s_client.V1PodTemplateSpec(
                    spec=k8s_client.V1PodSpec(
                        containers=[
                            k8s_client.V1Container(
                                name="deploy",
                                image=image,
                                command=command,
                                env=env_vars,
                            )
                        ],
                        restart_policy="Never",
                    )
                ),
                backoff_limit=1,
            ),
        )
        self._batch.create_namespaced_job(namespace=self._namespace, body=job)
        log.info("k8s_job_created", job_name=job_name)
        return job_name

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def schedule_cron(
        self,
        deploy_id: str,
        cron_expr: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        cron_name = f"deploy-cron-{deploy_id}"

        env_vars = [
            k8s_client.V1EnvVar(name="DEPLOY_ID", value=deploy_id),
        ]
        for k, v in (params or {}).items():
            env_vars.append(k8s_client.V1EnvVar(name=k, value=str(v)))

        cron_job = k8s_client.V1CronJob(
            metadata=k8s_client.V1ObjectMeta(name=cron_name, namespace=self._namespace),
            spec=k8s_client.V1CronJobSpec(
                schedule=cron_expr,
                job_template=k8s_client.V1JobTemplateSpec(
                    spec=k8s_client.V1JobSpec(
                        template=k8s_client.V1PodTemplateSpec(
                            spec=k8s_client.V1PodSpec(
                                containers=[
                                    k8s_client.V1Container(
                                        name="deploy",
                                        image="busybox",
                                        command=["/bin/sh", "-c", "echo deploy"],
                                        env=env_vars,
                                    )
                                ],
                                restart_policy="Never",
                            )
                        ),
                        backoff_limit=1,
                    )
                ),
            ),
        )
        self._batch.create_namespaced_cron_job(namespace=self._namespace, body=cron_job)
        log.info("k8s_cronjob_created", cron_name=cron_name, schedule=cron_expr)
        return cron_name

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def cancel_cron(self, schedule_id: str) -> None:
        self._batch.delete_namespaced_cron_job(name=schedule_id, namespace=self._namespace)
        log.info("k8s_cronjob_deleted", cron_name=schedule_id)
