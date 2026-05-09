from __future__ import annotations

import base64
import json
import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import ensure_runtime_dirs, split_args
from .state import state_dir
from .runtime import LlamaCppRuntime


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class KubernetesProvider:
    GPU_RESOURCES = {
        "nvidia.com/gpu": ("nvidia", "NVIDIA GPU"),
        "amd.com/gpu": ("amd", "AMD GPU"),
        "gpu.intel.com/i915": ("intel", "Intel GPU"),
    }

    def __init__(self, context: str | None, namespace: str | None, env: dict[str, str] | None = None):
        self.context = context or ""
        self.namespace = namespace or "anygpu"
        self.env = env

    def list_inventory(self, cluster_name: str) -> dict[str, Any]:
        result = self._run(["get", "nodes", "-o", "json"])
        base = {
            "provider": "kubernetes",
            "cluster": cluster_name,
            "context": self.context,
            "namespace": self.namespace,
            "status": "unavailable",
            "nodes": [],
            "runtime_support": [],
            "checks": [
                {
                    "name": "list kubernetes nodes",
                    "status": "pass" if result.returncode == 0 else "fail",
                }
            ],
            "inventory_source": "kubectl",
            "last_seen": now(),
        }
        if result.returncode != 0:
            base["error"] = (result.stderr or result.stdout or "kubectl could not list nodes").strip()
            return base
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as error:
            base["error"] = f"kubectl returned invalid node JSON: {error}"
            return base

        nodes = [self._parse_node(item) for item in payload.get("items", [])]
        runtimes = self._supported_runtimes(nodes)
        base.update(
            {
                "status": "available",
                "nodes": nodes,
                "runtime_support": runtimes,
                "checks": base["checks"] + [self._namespace_check()],
            }
        )
        return base

    def _parse_node(self, item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        labels = metadata.get("labels", {})
        capacity = status.get("capacity", {})
        allocatable = status.get("allocatable", {})
        accelerators = []
        for resource, (vendor, default_name) in self.GPU_RESOURCES.items():
            count = self._int_resource(capacity.get(resource))
            if count <= 0:
                continue
            accelerators.append(
                {
                    "vendor": vendor,
                    "name": self._accelerator_name(vendor, default_name, labels),
                    "count": count,
                    "allocatable": self._int_resource(allocatable.get(resource)),
                    "memory_gb": self._memory_gb(labels),
                    "resource": resource,
                }
            )
        return {
            "name": metadata.get("name", "unknown"),
            "available": self._node_ready(status.get("conditions", [])),
            "accelerators": accelerators,
            "runtimes": self._node_runtimes(accelerators),
            "kubelet_version": status.get("nodeInfo", {}).get("kubeletVersion"),
            "container_runtime": status.get("nodeInfo", {}).get("containerRuntimeVersion"),
        }

    def _namespace_check(self) -> dict[str, str]:
        result = self._run(["get", "namespace", self.namespace, "-o", "json"])
        return {
            "name": f"namespace {self.namespace}",
            "status": "pass" if result.returncode == 0 else "missing",
            "detail": (result.stderr or result.stdout or "").strip()[:240],
        }

    def _run(self, args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
        command = ["kubectl"]
        if self.context:
            command.extend(["--context", self.context])
        command.extend(args)
        try:
            return subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False, env=self.env)
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            return subprocess.CompletedProcess(command, 127, "", str(error))

    @staticmethod
    def _node_ready(conditions: list[dict[str, Any]]) -> bool:
        return any(condition.get("type") == "Ready" and condition.get("status") == "True" for condition in conditions)

    @staticmethod
    def _int_resource(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(float(str(value)))
        except ValueError:
            return 0

    @staticmethod
    def _memory_gb(labels: dict[str, str]) -> int:
        candidates = [
            labels.get("anygpu.ai/gpu-memory-gb"),
            labels.get("nvidia.com/gpu.memory"),
            labels.get("amd.com/gpu.memory"),
        ]
        for value in candidates:
            if not value:
                continue
            try:
                return int(float(str(value).replace("Gi", "").replace("GB", "")))
            except ValueError:
                continue
        return 0

    @staticmethod
    def _accelerator_name(vendor: str, default_name: str, labels: dict[str, str]) -> str:
        keys = {
            "nvidia": ["nvidia.com/gpu.product", "cloud.google.com/gke-accelerator", "node.kubernetes.io/instance-type"],
            "amd": ["amd.com/gpu.product", "node.kubernetes.io/instance-type"],
            "intel": ["gpu.intel.com/product", "node.kubernetes.io/instance-type"],
        }.get(vendor, [])
        for key in keys:
            value = labels.get(key)
            if value:
                return str(value).replace("-", " ")
        return default_name

    @staticmethod
    def _node_runtimes(accelerators: list[dict[str, Any]]) -> list[str]:
        if accelerators:
            return ["vllm", "sglang", "pytorch", "llama.cpp"]
        return ["pytorch", "llama.cpp"]

    @staticmethod
    def _supported_runtimes(nodes: list[dict[str, Any]]) -> list[str]:
        ordered = ["vllm", "sglang", "pytorch", "llama.cpp"]
        available = {runtime for node in nodes for runtime in node.get("runtimes", [])}
        return [runtime for runtime in ordered if runtime in available]


class DockerProvider:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def list_inventory(self) -> dict[str, Any]:
        docker = self._docker_status()
        gpus = self._discover_gpus() if docker["available"] else []
        return {
            "provider": "docker",
            "node_id": "local",
            "status": "available" if docker["available"] else "unavailable",
            "driver": "docker",
            "health": "healthy" if docker["available"] else "unavailable",
            "docker": docker,
            "gpus": gpus,
            "runtimes_supported": ["llama.cpp", "pytorch", "vllm"],
            "runtime_support": ["llama.cpp", "pytorch", "vllm"],
            "runtime_capabilities": {
                "llama.cpp": {
                    "model_format": ["gguf"],
                    "backends": ["cpu", "cuda", "metal", "vulkan", "hip"],
                    "serving_protocol": "openai-compatible",
                },
                "pytorch": {
                    "model_format": ["hf", "safetensors", "pickle"],
                    "requires": {"gpu": False},
                },
                "vllm": {
                    "model_format": ["hf", "safetensors"],
                    "requires": {"gpu": True, "cuda": ">=12.1", "memory_gb_min": 16},
                    "serving_protocol": "openai-compatible",
                },
            },
            "inventory_source": "docker_cli",
            "last_seen": now(),
        }

    def create_runtime(self, spec: dict[str, Any]) -> dict[str, Any]:
        runtime = spec.get("runtime")
        if not spec.get("model_path"):
            raise ValueError("model_path is required for Docker runtime creation")
        if runtime == "llama.cpp":
            return self._create_llama_cpp_runtime(spec)
        if runtime == "vllm":
            return self._create_vllm_runtime(spec)
        raise ValueError("Docker provider currently supports runtime=llama.cpp or runtime=vllm")

    def _create_llama_cpp_runtime(self, spec: dict[str, Any]) -> dict[str, Any]:
        model_path = Path(str(spec["model_path"])).expanduser()
        if not model_path.exists():
            raise ValueError(f"Model file does not exist: {model_path}")
        if model_path.suffix.lower() != ".gguf":
            raise ValueError("Docker llama.cpp serving requires a GGUF model")
        host = str(self.config.get("docker_runtime_host", "127.0.0.1"))
        port = int(spec.get("port") or self.allocate_port())
        container_port = int(self.config.get("docker_llama_cpp_container_port", 8080))
        container_name = spec.get("container_name") or f"anygpu-{self._safe_name(spec['name'])}"
        container_model_path = f"/models/{model_path.name}"
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{port}:{container_port}",
            "-v",
            f"{model_path.parent.resolve()}:/models:ro",
            str(self.config.get("docker_llama_cpp_image", "ghcr.io/ggml-org/llama.cpp:server")),
            "-m",
            container_model_path,
            "--host",
            "0.0.0.0",
            "--port",
            str(container_port),
            "--ctx-size",
            str(int(self.config.get("llama_cpp_ctx_size", 8192))),
        ]
        return {
            "provider": "docker",
            "runtime_id": spec.get("name") or f"docker-runtime-{int(time.time())}",
            "spec": spec,
            "runtime": "llama.cpp",
            "model_path": str(model_path),
            "host": host,
            "port": port,
            "container_port": container_port,
            "container_name": container_name,
            "container_model_path": container_model_path,
            "image": str(self.config.get("docker_llama_cpp_image", "ghcr.io/ggml-org/llama.cpp:server")),
            "command": command,
            "upstream_url": f"http://{host}:{port}",
            "status": "created",
            "created_at": now(),
        }

    def _create_vllm_runtime(self, spec: dict[str, Any]) -> dict[str, Any]:
        model_source = str(spec["model_path"])
        model_id = model_source.removeprefix("hf:")
        if not model_id:
            raise ValueError("vLLM serving requires an HF model id or model path")
        host = str(self.config.get("docker_runtime_host", "127.0.0.1"))
        port = int(spec.get("port") or self.allocate_port(preferred=int(self.config.get("docker_vllm_runtime_port_start", 8000))))
        container_port = int(self.config.get("docker_vllm_container_port", 8000))
        container_name = spec.get("container_name") or f"anygpu-{self._safe_name(spec['name'])}"
        image = str(self.config.get("docker_vllm_image", "vllm/vllm-openai:latest"))
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--gpus",
            "all",
            "-p",
            f"{port}:{container_port}",
            image,
            "--model",
            model_id,
            "--host",
            "0.0.0.0",
            "--port",
            str(container_port),
        ]
        return {
            "provider": "docker",
            "runtime_id": spec.get("name") or f"docker-runtime-{int(time.time())}",
            "spec": spec,
            "runtime": "vllm",
            "model_source": model_source,
            "model_id": model_id,
            "host": host,
            "port": port,
            "container_port": container_port,
            "container_name": container_name,
            "image": image,
            "command": command,
            "upstream_url": f"http://{host}:{port}",
            "status": "created",
            "created_at": now(),
        }

    def start_runtime(self, handle: dict[str, Any]) -> dict[str, Any]:
        result = self._run(handle["command"], timeout=30.0)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "docker run failed").strip())
        container_id = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else handle["container_name"]
        started = {
            **handle,
            "container_id": container_id,
            "started_at": now(),
            "status": "running",
            "health": "starting",
            "simulated": False,
        }
        health = self.wait_for_runtime_health(started, timeout_seconds=float(self.config.get("docker_health_timeout_seconds", 30)))
        started["health"] = "healthy" if health["healthy"] else health["status"]
        return started

    def wait_for_runtime_health(self, deployment: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        latest = self.health_check(deployment)
        while time.time() < deadline:
            latest = self.health_check(deployment)
            if latest["healthy"]:
                return latest
            time.sleep(0.25)
        return latest

    def stop_runtime(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        target = self._container_target(deployment)
        stop = self._run(["docker", "stop", target])
        rm = self._run(["docker", "rm", target])
        stop_text = (stop.stderr or stop.stdout or "").strip()
        rm_text = (rm.stderr or rm.stdout or "").strip()
        missing = "No such container" in stop_text or "No such container" in rm_text
        if stop.returncode == 0 or rm.returncode == 0:
            status = "stopped"
        elif missing:
            status = "not_running"
        else:
            status = "stop_failed"
        stopped = dict(deployment) if isinstance(deployment, dict) else {"deployment_id": deployment}
        stopped.update({"provider": "docker", "status": status, "health": status, "stopped_at": now()})
        if stop.returncode != 0 and stop_text:
            stopped["stop_error"] = stop_text
        if rm.returncode != 0 and rm_text:
            stopped["remove_error"] = rm_text
        return stopped

    def inspect_runtime(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        target = self._container_target(deployment)
        result = self._run(["docker", "inspect", "--format", "{{json .State}}", target])
        if result.returncode != 0:
            return {"provider": "docker", "deployment_id": target, "status": "unknown", "error": result.stderr.strip()}
        raw = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "{}"
        try:
            state = json.loads(raw)
        except json.JSONDecodeError:
            state = {}
        health = state.get("Health", {}).get("Status")
        status = health or state.get("Status") or "unknown"
        return {"provider": "docker", "deployment_id": target, "status": status, "state": state}

    def health_check(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        inspection = self.inspect_runtime(deployment)
        return {
            "provider": "docker",
            "deployment_id": inspection["deployment_id"],
            "healthy": inspection["status"] in {"running", "healthy"},
            "status": inspection["status"],
        }

    def logs(self, deployment: str | dict[str, Any], lines: int = 200) -> str:
        target = self._container_target(deployment)
        result = self._run(["docker", "logs", "--tail", str(lines), target])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "docker logs failed").strip())
        return result.stdout

    def allocate_port(self, preferred: int | None = None) -> int:
        host = str(self.config.get("docker_runtime_host", "127.0.0.1"))
        start = int(preferred or self.config.get("docker_runtime_port_start", 8080))
        end = int(self.config.get("docker_runtime_port_end", 8180))
        for port in range(start, end + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind((host, port))
                except OSError:
                    continue
                return port
        raise RuntimeError(f"No free Docker runtime ports available from {start} to {end}")

    def _docker_status(self) -> dict[str, Any]:
        version = self._run(["docker", "version", "--format", "{{.Server.Version}}"])
        if version.returncode != 0:
            fallback = self._run(["docker", "version"])
            if fallback.returncode != 0:
                return {
                    "available": False,
                    "version": None,
                    "error": (fallback.stderr or fallback.stdout or "docker command unavailable").strip(),
                }
            version_text = fallback.stdout.strip().splitlines()[0] if fallback.stdout.strip() else "unknown"
        else:
            version_text = version.stdout.strip() or "unknown"

        runtimes = self._docker_runtimes()
        return {
            "available": True,
            "version": version_text,
            "runtimes": runtimes,
            "nvidia_runtime": "nvidia" in runtimes,
        }

    def _docker_runtimes(self) -> list[str]:
        result = self._run(["docker", "info", "--format", "{{json .Runtimes}}"])
        if result.returncode != 0:
            return []
        raw = result.stdout.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            return sorted(str(key) for key in data.keys())
        return []

    def _discover_gpus(self) -> list[dict[str, Any]]:
        result = self._run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ]
        )
        if result.returncode != 0:
            return []
        gpus = []
        for line in result.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 3:
                continue
            name, memory_mb, driver = parts[:3]
            try:
                memory_gb = round(int(float(memory_mb)) / 1024)
            except ValueError:
                memory_gb = 0
            gpus.append(
                {
                    "vendor": "nvidia",
                    "name": name,
                    "memory_gb": memory_gb,
                    "driver": driver,
                    "cuda": "available",
                }
            )
        return gpus

    @staticmethod
    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value).strip("-") or "runtime"

    @staticmethod
    def _container_target(deployment: str | dict[str, Any]) -> str:
        if isinstance(deployment, dict):
            return str(deployment.get("container_id") or deployment.get("container_name") or deployment.get("deployment_id"))
        return deployment

    @staticmethod
    def _run(command: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            return subprocess.CompletedProcess(command, 127, "", str(error))


class VultrProvider:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.base_url = str(config.get("vultr_api_base_url") or "https://api.vultr.com/v2").rstrip("/")

    def create_runtime(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not self.config.get("vultr_api_key"):
            raise ValueError("vultr_api_key is required for Vultr cloud deployment")
        runtime = str(spec.get("runtime") or "")
        if runtime not in {"vllm", "llama.cpp"}:
            raise ValueError("Vultr provider currently supports runtime=vllm or runtime=llama.cpp")
        plan = str(spec.get("plan") or "")
        region = str(spec.get("region") or "")
        if not plan:
            raise ValueError("Vultr cloud deployment requires a plan")
        if not region:
            raise ValueError("Vultr cloud deployment requires a region")
        deployment_kind = str(spec.get("deployment_kind") or self._deployment_kind_for_plan(plan))
        resource_type = "bare-metal" if deployment_kind == "bare-metal" else "instance"
        port = self._runtime_port(runtime)
        user_data = self._build_user_data(spec, port)
        body: dict[str, Any] = {
            "region": region,
            "plan": plan,
            "os_id": int(spec.get("os_id") or self.config.get("vultr_os_id") or 2284),
            "label": spec.get("name") or "anygpu-runtime",
            "hostname": spec.get("hostname") or self._safe_hostname(str(spec.get("name") or "anygpu-runtime")),
            "tags": ["anygpu", f"runtime:{runtime}"],
            "user_data": base64.b64encode(user_data.encode()).decode(),
        }
        ssh_keys = spec.get("ssh_key_ids") or self.config.get("vultr_ssh_key_ids")
        if ssh_keys:
            body["sshkey_id"] = [value.strip() for value in str(ssh_keys).split(",") if value.strip()]
        firewall_group_id = spec.get("firewall_group_id") or self.config.get("vultr_firewall_group_id")
        if firewall_group_id:
            body["firewall_group_id"] = str(firewall_group_id)

        path = "/bare-metals" if resource_type == "bare-metal" else "/instances"
        payload = self._request("POST", path, body)
        resource_key = "bare_metal" if resource_type == "bare-metal" else "instance"
        resource = payload.get(resource_key) if isinstance(payload, dict) else {}
        if not isinstance(resource, dict):
            resource = {}
        vultr_id = str(resource.get("id") or "")
        if not vultr_id:
            raise RuntimeError("Vultr create response did not include a resource id")
        main_ip = str(resource.get("main_ip") or "")
        upstream_url = f"http://{main_ip}:{port}" if main_ip else None
        return {
            "provider": "vultr",
            "runtime_id": vultr_id,
            "vultr_id": vultr_id,
            "resource_type": resource_type,
            "runtime": runtime,
            "model_source": str(spec.get("model_path") or ""),
            "region": region,
            "plan": plan,
            "deployment_kind": deployment_kind,
            "host": main_ip,
            "port": port,
            "upstream_url": upstream_url,
            "status": str(resource.get("status") or "provisioning"),
            "server_status": resource.get("server_status"),
            "health": "provisioning",
            "created_at": now(),
            "simulated": False,
            "bootstrap": {
                "kind": "cloud-init",
                "runtime": runtime,
                "image": self._runtime_image(runtime),
                "port": port,
            },
        }

    def inspect_runtime(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        resource_type = self._resource_type(deployment)
        vultr_id = self._resource_id(deployment)
        path = f"/bare-metals/{vultr_id}" if resource_type == "bare-metal" else f"/instances/{vultr_id}"
        payload = self._request("GET", path)
        resource_key = "bare_metal" if resource_type == "bare-metal" else "instance"
        resource = payload.get(resource_key) if isinstance(payload, dict) else {}
        if not isinstance(resource, dict):
            resource = {}
        port = int(deployment.get("port") or self._runtime_port(str(deployment.get("runtime") or "vllm"))) if isinstance(deployment, dict) else 0
        main_ip = str(resource.get("main_ip") or "")
        upstream_url = f"http://{main_ip}:{port}" if main_ip and port else None
        status = str(resource.get("server_status") or resource.get("status") or "unknown")
        return {
            "provider": "vultr",
            "deployment_id": vultr_id,
            "vultr_id": vultr_id,
            "resource_type": resource_type,
            "status": status,
            "host": main_ip,
            "upstream_url": upstream_url,
            "resource": resource,
        }

    def health_check(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        inspection = self.inspect_runtime(deployment)
        upstream = inspection.get("upstream_url") or (deployment.get("upstream_url") if isinstance(deployment, dict) else None)
        if not upstream:
            return {**inspection, "healthy": False, "health": "provisioning"}
        try:
            with urllib.request.urlopen(f"{upstream}/health", timeout=1.0) as response:
                healthy = 200 <= response.status < 300
        except (OSError, urllib.error.URLError):
            healthy = inspection["status"] in {"ok", "active", "running"}
        return {**inspection, "healthy": healthy, "health": "healthy" if healthy else inspection["status"]}

    def stop_runtime(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        resource_type = self._resource_type(deployment)
        vultr_id = self._resource_id(deployment)
        path = f"/bare-metals/{vultr_id}" if resource_type == "bare-metal" else f"/instances/{vultr_id}"
        self._request("DELETE", path)
        stopped = dict(deployment) if isinstance(deployment, dict) else {"vultr_id": vultr_id}
        stopped.update(
            {
                "provider": "vultr",
                "vultr_id": vultr_id,
                "resource_type": resource_type,
                "status": "deleted",
                "health": "stopped",
                "stopped_at": now(),
            }
        )
        return stopped

    def logs(self, deployment: str | dict[str, Any], lines: int = 200) -> str:
        target = self._resource_id(deployment)
        return (
            f"Vultr runtime {target} was bootstrapped with cloud-init. "
            "Remote log streaming is not implemented yet; inspect /var/log/cloud-init-output.log on the instance."
        )

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.get('vultr_api_key')}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode()
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"Vultr API {method} {path} failed: {error.code} {detail}") from error
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Vultr API {method} {path} returned invalid JSON") from error
        return parsed if isinstance(parsed, dict) else {}

    def _build_user_data(self, spec: dict[str, Any], port: int) -> str:
        runtime = str(spec["runtime"])
        image = self._runtime_image(runtime)
        model_source = str(spec["model_path"])
        if runtime == "vllm":
            model_id = model_source.removeprefix("hf:")
            runtime_command = (
                f"docker run -d --restart unless-stopped --gpus all --name anygpu-runtime "
                f"-p {port}:{port} {image} --model {model_id} --host 0.0.0.0 --port {port}"
            )
        else:
            runtime_command = (
                f"docker run -d --restart unless-stopped --name anygpu-runtime "
                f"-p {port}:{port} {image} -m {model_source} --host 0.0.0.0 --port {port}"
            )
        return "\n".join(
            [
                "#cloud-config",
                "package_update: true",
                "packages:",
                "  - docker.io",
                "runcmd:",
                "  - systemctl enable --now docker",
                f"  - {runtime_command}",
                "",
            ]
        )

    def _runtime_image(self, runtime: str) -> str:
        if runtime == "vllm":
            return str(self.config.get("docker_vllm_image", "vllm/vllm-openai:latest"))
        return str(self.config.get("docker_llama_cpp_image", "ghcr.io/ggml-org/llama.cpp:server"))

    def _runtime_port(self, runtime: str) -> int:
        if runtime == "vllm":
            return int(self.config.get("docker_vllm_container_port", 8000))
        return int(self.config.get("docker_llama_cpp_container_port", 8080))

    @staticmethod
    def _deployment_kind_for_plan(plan: str) -> str:
        return "bare-metal" if plan.startswith("vbm-") else "cloud-gpu"

    @staticmethod
    def _safe_hostname(value: str) -> str:
        hostname = "".join(char.lower() if char.isalnum() or char == "-" else "-" for char in value)
        return hostname.strip("-")[:63] or "anygpu-runtime"

    @staticmethod
    def _resource_type(deployment: str | dict[str, Any]) -> str:
        if isinstance(deployment, dict):
            return str(deployment.get("resource_type") or "instance")
        return "instance"

    @staticmethod
    def _resource_id(deployment: str | dict[str, Any]) -> str:
        if isinstance(deployment, dict):
            return str(deployment.get("vultr_id") or deployment.get("runtime_id") or deployment.get("deployment_id"))
        return deployment


class VastProvider:
    GPU_NAMES = {
        "rtx-4090": ["RTX 4090", "NVIDIA GeForce RTX 4090", "RTX_4090"],
        "a100": ["A100", "NVIDIA A100", "NVIDIA A100-SXM4-80GB", "NVIDIA A100 80GB PCIe"],
        "h100": ["H100", "NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL"],
        "h200": ["H200", "NVIDIA H200"],
        "l40s": ["L40S", "NVIDIA L40S", "NVIDIA L40"],
        "l4": ["L4", "NVIDIA L4"],
        "mi300x": ["MI300X", "AMD Instinct MI300X OAM"],
    }

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.root_url = str(config.get("vast_api_root_url") or "https://console.vast.ai/api/v0").rstrip("/")

    def create_runtime(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not self.config.get("vast_api_key"):
            raise ValueError("vast_api_key is required for Vast cloud deployment")
        runtime = str(spec.get("runtime") or "")
        if runtime not in {"vllm", "llama.cpp"}:
            raise ValueError("Vast provider currently supports runtime=vllm or runtime=llama.cpp")
        offer = self._select_offer(spec)
        offer_id = str(offer["id"])
        port = self._runtime_port(runtime)
        body = self._create_body(spec, runtime, port)
        payload = self._request("PUT", f"/asks/{offer_id}/", body)
        if not payload.get("success"):
            raise RuntimeError(f"Vast create instance failed: {payload}")
        instance_id = str(payload.get("new_contract") or "")
        if not instance_id:
            raise RuntimeError("Vast create response did not include new_contract")
        inspected = self.inspect_runtime({"vast_instance_id": instance_id, "runtime": runtime, "port": port})
        upstream_url = inspected.get("upstream_url")
        return {
            "provider": "vast",
            "runtime_id": instance_id,
            "vast_instance_id": instance_id,
            "offer_id": offer_id,
            "runtime": runtime,
            "model_source": str(spec.get("model_path") or ""),
            "host": inspected.get("host"),
            "port": int(inspected.get("port") or port),
            "upstream_url": upstream_url,
            "status": inspected.get("status", "provisioning"),
            "health": "provisioning",
            "region": str(offer.get("geolocation") or "unknown"),
            "price_per_hour_usd": float(offer.get("dph_total") or offer.get("dph_base") or 0.0),
            "gpu_name": offer.get("gpu_name"),
            "gpu_count": int(float(offer.get("num_gpus") or 1)),
            "created_at": now(),
            "simulated": False,
            "bootstrap": {
                "kind": "vast-onstart",
                "runtime": runtime,
                "image": body["image"],
                "port": port,
            },
        }

    def inspect_runtime(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        instance_id = self._instance_id(deployment)
        runtime = str(deployment.get("runtime") or "vllm") if isinstance(deployment, dict) else "vllm"
        container_port = int(deployment.get("port") or self._runtime_port(runtime)) if isinstance(deployment, dict) else self._runtime_port(runtime)
        payload = self._request("GET", f"/instances/{instance_id}/")
        instance = self._instance_payload(payload)
        host = str(instance.get("ssh_host") or instance.get("public_ipaddr") or instance.get("public_ip") or instance.get("ipaddr") or "")
        host_port = self._mapped_port(instance, container_port) or container_port
        upstream_url = f"http://{host}:{host_port}" if host else None
        return {
            "provider": "vast",
            "deployment_id": instance_id,
            "vast_instance_id": instance_id,
            "status": str(instance.get("actual_status") or instance.get("status") or "unknown"),
            "host": host,
            "port": host_port,
            "upstream_url": upstream_url,
            "instance": instance,
        }

    def health_check(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        inspection = self.inspect_runtime(deployment)
        upstream = inspection.get("upstream_url")
        healthy = False
        if upstream:
            try:
                with urllib.request.urlopen(f"{upstream}/health", timeout=1.0) as response:
                    healthy = 200 <= response.status < 300
            except (OSError, urllib.error.URLError):
                healthy = inspection["status"] in {"running", "loading"}
        return {**inspection, "healthy": healthy, "health": "healthy" if healthy else inspection["status"]}

    def stop_runtime(self, deployment: str | dict[str, Any]) -> dict[str, Any]:
        instance_id = self._instance_id(deployment)
        self._request("DELETE", f"/instances/{instance_id}/")
        stopped = dict(deployment) if isinstance(deployment, dict) else {"vast_instance_id": instance_id}
        stopped.update(
            {
                "provider": "vast",
                "vast_instance_id": instance_id,
                "status": "destroyed",
                "health": "stopped",
                "stopped_at": now(),
            }
        )
        return stopped

    def logs(self, deployment: str | dict[str, Any], lines: int = 200) -> str:
        instance_id = self._instance_id(deployment)
        return (
            f"Vast runtime {instance_id} was started through onstart. "
            "Remote SSH log streaming is not implemented yet; inspect the instance through Vast SSH/Jupyter."
        )

    def _select_offer(self, spec: dict[str, Any]) -> dict[str, Any]:
        if spec.get("offer_id"):
            return {"id": spec["offer_id"], "dph_total": spec.get("max_price") or 0.0, "num_gpus": 1, "gpu_name": spec.get("accelerator")}
        offers = self.search_offers(
            accelerator=str(spec.get("accelerator") or "rtx-4090"),
            max_price=float(spec.get("max_price") or 1.0),
            limit=int(spec.get("limit") or 10),
        )
        if not offers:
            raise ValueError("No Vast offers matched the requested accelerator/price filters")
        return sorted(offers, key=lambda offer: float(offer.get("dph_total") or offer.get("dph_base") or 999999))[0]

    def search_offers(self, accelerator: str, max_price: float, limit: int = 10) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "limit": int(limit),
            "type": "on-demand",
            "verified": {"eq": True},
            "rentable": {"eq": True},
            "rented": {"eq": False},
            "dph_total": {"lte": float(max_price)},
        }
        gpu_names = self.GPU_NAMES.get(accelerator, [accelerator])
        if gpu_names:
            body["gpu_name"] = {"in": gpu_names}
        payload = self._request("POST", "/bundles/", body)
        offers = payload.get("offers", []) if isinstance(payload, dict) else []
        return [offer for offer in offers if isinstance(offer, dict)]

    def _create_body(self, spec: dict[str, Any], runtime: str, port: int) -> dict[str, Any]:
        image = self._runtime_image(runtime)
        model_source = str(spec.get("model_path") or "")
        model_id = model_source.removeprefix("hf:")
        env = {
            "MODEL_ID": model_id,
            f"-p {port}:{port}": "1",
        }
        if runtime == "vllm":
            onstart = f"env >> /etc/environment; nohup vllm serve $MODEL_ID --host 0.0.0.0 --port {port} > /tmp/anygpu-vllm.log 2>&1 &"
        else:
            onstart = f"env >> /etc/environment; nohup llama-server -m $MODEL_ID --host 0.0.0.0 --port {port} > /tmp/anygpu-llama.log 2>&1 &"
        return {
            "image": image,
            "label": spec.get("name") or "anygpu-runtime",
            "disk": int(spec.get("disk_gb") or self.config.get("vast_default_disk_gb") or 30),
            "runtype": "ssh_direct",
            "target_state": "running",
            "cancel_unavail": True,
            "env": env,
            "onstart": onstart,
        }

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.root_url}{path}",
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.get('vast_api_key')}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode()
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"Vast API {method} {path} failed: {error.code} {detail}") from error
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Vast API {method} {path} returned invalid JSON") from error
        return parsed if isinstance(parsed, dict) else {}

    def _runtime_image(self, runtime: str) -> str:
        if runtime == "vllm":
            return str(self.config.get("docker_vllm_image", "vllm/vllm-openai:latest"))
        return str(self.config.get("docker_llama_cpp_image", "ghcr.io/ggml-org/llama.cpp:server"))

    def _runtime_port(self, runtime: str) -> int:
        if runtime == "vllm":
            return int(self.config.get("docker_vllm_container_port", 8000))
        return int(self.config.get("docker_llama_cpp_container_port", 8080))

    @staticmethod
    def _instance_payload(payload: dict[str, Any]) -> dict[str, Any]:
        instance = payload.get("instances") or payload.get("instance")
        if isinstance(instance, list):
            return instance[0] if instance and isinstance(instance[0], dict) else {}
        return instance if isinstance(instance, dict) else {}

    @staticmethod
    def _mapped_port(instance: dict[str, Any], container_port: int) -> int | None:
        ports = instance.get("ports") or instance.get("ports_info") or {}
        if isinstance(ports, dict):
            for key, values in ports.items():
                if str(container_port) not in str(key):
                    continue
                if isinstance(values, list) and values:
                    host_port = values[0].get("HostPort") if isinstance(values[0], dict) else None
                    if host_port:
                        return int(host_port)
                if isinstance(values, dict) and values.get("HostPort"):
                    return int(values["HostPort"])
        return None

    @staticmethod
    def _instance_id(deployment: str | dict[str, Any]) -> str:
        if isinstance(deployment, dict):
            return str(deployment.get("vast_instance_id") or deployment.get("runtime_id") or deployment.get("deployment_id"))
        return deployment


class LocalProvider:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        ensure_runtime_dirs(config)

    def allocate_port(self, preferred: int | None = None) -> int:
        host = self.config["local_runtime_host"]
        start = preferred or int(self.config["local_runtime_port_start"])
        end = int(self.config["local_runtime_port_end"])
        for port in range(start, end + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind((host, port))
                except OSError:
                    continue
                return port
        raise RuntimeError(f"No free local ports available from {start}")

    def launch_llama_server(self, deployment_name: str, model_path: str, port: int | None = None) -> dict[str, Any]:
        server_path = self.config.get("llama_cpp_server_path")
        if not server_path:
            raise ValueError("llama_cpp_server_path is not configured")
        host = self.config["local_runtime_host"]
        selected_port = self.allocate_port(port)
        logs_dir = state_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        logs_path = logs_dir / f"{deployment_name}.log"
        command = LlamaCppRuntime(self.config).build_server_command(model_path, host, selected_port)
        log_file = logs_path.open("ab")
        process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
        metadata = {
            "pid": process.pid,
            "command": command,
            "provider": "local",
            "host": host,
            "port": selected_port,
            "upstream_url": f"http://{host}:{selected_port}",
            "model_path": model_path,
            "started_at": now(),
            "health": "starting",
            "health_path": self.config["llama_cpp_health_path"],
            "health_check_type": "unknown",
            "logs_path": str(logs_path),
            "runtime": "llama.cpp",
            "simulated": False,
        }
        if self.wait_for_health(metadata, timeout_seconds=float(self.config["llama_cpp_health_timeout_seconds"])):
            metadata["health"] = "healthy"
        else:
            metadata["health"] = "unhealthy"
        return metadata

    def wait_for_health(self, process: dict[str, Any], timeout_seconds: float) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.health_check(process):
                return True
            time.sleep(0.05)
        return False

    def health_check(self, process: dict[str, Any]) -> bool:
        pid = int(process["pid"])
        if not self.pid_alive(pid):
            return False
        try:
            health_path = process.get("health_path") or self.config["llama_cpp_health_path"]
            with urllib.request.urlopen(f"{process['upstream_url']}{health_path}", timeout=0.5) as response:
                process["health_check_type"] = "http"
                return 200 <= response.status < 300
        except (OSError, urllib.error.URLError):
            if self._tcp_open(process["host"], int(process["port"])):
                process["health_check_type"] = "tcp_process"
                return True
            return False

    def tail_logs(self, process: dict[str, Any], lines: int = 80) -> str:
        path = Path(process["logs_path"])
        if not path.exists():
            return ""
        content = path.read_text(errors="replace").splitlines()
        return "\n".join(content[-lines:])

    def stop(self, process: dict[str, Any]) -> dict[str, Any]:
        pid = int(process["pid"])
        if self.pid_alive(pid):
            self._signal_process_group(pid, signal.SIGTERM)
            deadline = time.time() + 3.0
            while time.time() < deadline:
                if not self.pid_alive(pid):
                    break
                time.sleep(0.05)
            if self.pid_alive(pid):
                self._signal_process_group(pid, signal.SIGKILL)
                time.sleep(0.1)
        stopped = dict(process)
        if self.pid_alive(pid):
            stopped["health"] = "stop_failed"
            stopped["stop_error"] = "process is still alive after SIGTERM/SIGKILL"
        else:
            stopped["health"] = "stopped"
            stopped["stopped_at"] = now()
        return stopped

    @staticmethod
    def pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _signal_process_group(pid: int, sig: signal.Signals) -> bool:
        try:
            os.killpg(pid, sig)
            return True
        except OSError:
            try:
                os.kill(pid, sig)
                return True
            except OSError:
                return False

    @staticmethod
    def _tcp_open(host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((host, port)) == 0
