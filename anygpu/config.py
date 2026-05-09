from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any

from .state import state_dir


CONFIG_DEFAULTS: dict[str, Any] = {
    "llama_cpp_server_path": None,
    "llama_cpp_server_args": "",
    "llama_cpp_cli_path": None,
    "llama_cpp_cli_args": "",
    "llama_cpp_health_path": "/health",
    "llama_cpp_health_timeout_seconds": 30,
    "llama_cpp_ctx_size": 8192,
    "model_cache_path": None,
    "local_runtime_host": "127.0.0.1",
    "local_runtime_port_start": 18080,
    "local_runtime_port_end": 18280,
    "docker_runtime_host": "127.0.0.1",
    "docker_runtime_port_start": 8080,
    "docker_runtime_port_end": 8180,
    "docker_llama_cpp_image": "ghcr.io/ggml-org/llama.cpp:server",
    "docker_llama_cpp_container_port": 8080,
    "docker_health_timeout_seconds": 30,
    "docker_vllm_image": "vllm/vllm-openai:latest",
    "docker_vllm_runtime_port_start": 8000,
    "docker_vllm_runtime_port_end": 8079,
    "docker_vllm_container_port": 8000,
    "vast_api_key": None,
    "vast_api_base_url": "https://console.vast.ai/api/v0/bundles/",
    "vast_api_root_url": "https://console.vast.ai/api/v0",
    "vast_default_disk_gb": 30,
    "vultr_api_key": None,
    "vultr_api_base_url": "https://api.vultr.com/v2",
    "vultr_os_id": 2284,
    "vultr_ssh_key_ids": "",
    "vultr_firewall_group_id": "",
}

ENV_TO_CONFIG = {
    "ANYGPU_LLAMA_CPP_SERVER_PATH": "llama_cpp_server_path",
    "ANYGPU_LLAMA_CPP_SERVER_ARGS": "llama_cpp_server_args",
    "ANYGPU_LLAMA_CPP_CLI_PATH": "llama_cpp_cli_path",
    "ANYGPU_LLAMA_CPP_CLI_ARGS": "llama_cpp_cli_args",
    "ANYGPU_LLAMA_CPP_HEALTH_PATH": "llama_cpp_health_path",
    "ANYGPU_LLAMA_CPP_HEALTH_TIMEOUT_SECONDS": "llama_cpp_health_timeout_seconds",
    "ANYGPU_LLAMA_CPP_CTX_SIZE": "llama_cpp_ctx_size",
    "ANYGPU_MODEL_CACHE_PATH": "model_cache_path",
    "ANYGPU_LOCAL_RUNTIME_HOST": "local_runtime_host",
    "ANYGPU_LOCAL_RUNTIME_PORT_START": "local_runtime_port_start",
    "ANYGPU_LOCAL_RUNTIME_PORT_END": "local_runtime_port_end",
    "ANYGPU_DEFAULT_HOST": "local_runtime_host",
    "ANYGPU_DEFAULT_PORT_START": "local_runtime_port_start",
    "ANYGPU_DOCKER_RUNTIME_HOST": "docker_runtime_host",
    "ANYGPU_DOCKER_RUNTIME_PORT_START": "docker_runtime_port_start",
    "ANYGPU_DOCKER_RUNTIME_PORT_END": "docker_runtime_port_end",
    "ANYGPU_DOCKER_LLAMA_CPP_IMAGE": "docker_llama_cpp_image",
    "ANYGPU_DOCKER_LLAMA_CPP_CONTAINER_PORT": "docker_llama_cpp_container_port",
    "ANYGPU_DOCKER_HEALTH_TIMEOUT_SECONDS": "docker_health_timeout_seconds",
    "ANYGPU_DOCKER_VLLM_IMAGE": "docker_vllm_image",
    "ANYGPU_DOCKER_VLLM_RUNTIME_PORT_START": "docker_vllm_runtime_port_start",
    "ANYGPU_DOCKER_VLLM_RUNTIME_PORT_END": "docker_vllm_runtime_port_end",
    "ANYGPU_DOCKER_VLLM_CONTAINER_PORT": "docker_vllm_container_port",
    "ANYGPU_VAST_API_KEY": "vast_api_key",
    "VAST_AI_API_KEY": "vast_api_key",
    "ANYGPU_VAST_API_BASE_URL": "vast_api_base_url",
    "ANYGPU_VAST_API_ROOT_URL": "vast_api_root_url",
    "ANYGPU_VAST_DEFAULT_DISK_GB": "vast_default_disk_gb",
    "ANYGPU_VULTR_API_KEY": "vultr_api_key",
    "VULTR_API_KEY": "vultr_api_key",
    "ANYGPU_VULTR_API_BASE_URL": "vultr_api_base_url",
    "ANYGPU_VULTR_OS_ID": "vultr_os_id",
    "ANYGPU_VULTR_SSH_KEY_IDS": "vultr_ssh_key_ids",
    "ANYGPU_VULTR_FIREWALL_GROUP_ID": "vultr_firewall_group_id",
}


def load_config(stored: dict[str, Any] | None = None) -> dict[str, Any]:
    config = dict(CONFIG_DEFAULTS)
    config.update(stored or {})
    for env_key, value in _load_dotenv().items():
        config_key = ENV_TO_CONFIG.get(env_key)
        if config_key:
            config[config_key] = value
    for env_key, config_key in ENV_TO_CONFIG.items():
        if env_key in os.environ:
            config[config_key] = os.environ[env_key]
    if not config["model_cache_path"]:
        config["model_cache_path"] = str(state_dir() / "models")
    if "default_host" in config and "local_runtime_host" not in (stored or {}):
        config["local_runtime_host"] = config["default_host"]
    if "default_port_start" in config and "local_runtime_port_start" not in (stored or {}):
        config["local_runtime_port_start"] = config["default_port_start"]
    config["local_runtime_port_start"] = int(config["local_runtime_port_start"])
    config["local_runtime_port_end"] = int(config["local_runtime_port_end"])
    config["llama_cpp_ctx_size"] = int(config["llama_cpp_ctx_size"])
    config["llama_cpp_health_timeout_seconds"] = float(config["llama_cpp_health_timeout_seconds"])
    config["docker_runtime_port_start"] = int(config["docker_runtime_port_start"])
    config["docker_runtime_port_end"] = int(config["docker_runtime_port_end"])
    config["docker_llama_cpp_container_port"] = int(config["docker_llama_cpp_container_port"])
    config["docker_health_timeout_seconds"] = float(config["docker_health_timeout_seconds"])
    config["docker_vllm_runtime_port_start"] = int(config["docker_vllm_runtime_port_start"])
    config["docker_vllm_runtime_port_end"] = int(config["docker_vllm_runtime_port_end"])
    config["docker_vllm_container_port"] = int(config["docker_vllm_container_port"])
    config["vast_default_disk_gb"] = int(config["vast_default_disk_gb"])
    config["vultr_os_id"] = int(config["vultr_os_id"])
    return config


def _load_dotenv(path: Path | None = None) -> dict[str, str]:
    env_path = path or Path.cwd() / ".env"
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key] = value
    return values


def split_args(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return shlex.split(value)


def ensure_runtime_dirs(config: dict[str, Any]) -> None:
    Path(config["model_cache_path"]).mkdir(parents=True, exist_ok=True)
    (state_dir() / "logs").mkdir(parents=True, exist_ok=True)
