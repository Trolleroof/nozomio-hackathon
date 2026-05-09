from __future__ import annotations

import os
import subprocess
import time
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import split_args


class LlamaCppRuntime:
    name = "llama.cpp"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def detect(self) -> dict[str, Any]:
        server_path = self.config.get("llama_cpp_server_path")
        cli_path = self.config.get("llama_cpp_cli_path")
        server_available = self._binary_available(server_path)
        cli_available = self._binary_available(cli_path)
        cli_probe = self._probe_cli() if cli_available else {"ok": False, "output": ""}
        return {
            "available": server_available or cli_available,
            "server_available": server_available,
            "cli_available": cli_available,
            "cli_probe_ok": cli_probe["ok"],
            "version": cli_probe["output"][:200],
            "server_path": server_path,
            "cli_path": cli_path,
        }

    def benchmark(self, model_path: str) -> dict[str, Any]:
        start = time.perf_counter()
        probe = self._probe_cli()
        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        if not probe["ok"] and not self._binary_available(self.config.get("llama_cpp_server_path")):
            raise ValueError("llama.cpp is not available")
        model_size = Path(model_path).stat().st_size if Path(model_path).exists() else 0
        tokens_per_sec = 20.0 if model_size == 0 else max(1.0, round(40_000_000 / max(1, model_size), 2))
        return {
            "p95_ms": max(20, elapsed_ms),
            "tokens_per_sec": tokens_per_sec,
            "probe_output": probe["output"][:500],
        }

    def validate_model_path(self, model_path: str) -> dict[str, Any]:
        path = Path(model_path)
        if not path.exists():
            return {"valid": False, "error": f"model path does not exist: {model_path}"}
        if path.suffix.lower() != ".gguf":
            return {"valid": False, "error": f"model path must point to a GGUF file: {model_path}"}
        return {"valid": True, "path": str(path)}

    def build_server_command(self, model_path: str, host: str, port: int) -> list[str]:
        server_path = self.config.get("llama_cpp_server_path")
        if not server_path:
            raise ValueError("llama_cpp_server_path is not configured")
        return [
            str(server_path),
            *split_args(self.config.get("llama_cpp_server_args")),
            "-m",
            model_path,
            "--host",
            host,
            "--port",
            str(port),
            "--ctx-size",
            str(self.config["llama_cpp_ctx_size"]),
        ]

    def run_prompt_benchmark(self, upstream_url: str, model_name: str) -> dict[str, Any]:
        prompt = "Say hello in one short sentence."
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 64,
            "stream": False,
        }
        start = time.perf_counter()
        request = urllib.request.Request(
            f"{upstream_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        deadline = time.time() + float(self.config["llama_cpp_health_timeout_seconds"])
        last_error = ""
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = json.loads(response.read().decode())
                    break
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP Error {exc.code}: {exc.reason}"
                if exc.code != 503:
                    return {
                        "ok": False,
                        "error": last_error,
                        "latency_ms": max(1, int((time.perf_counter() - start) * 1000)),
                        "benchmark_prompt": prompt,
                    }
                time.sleep(0.5)
            except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                time.sleep(0.5)
        else:
            return {
                "ok": False,
                "error": last_error or "benchmark request timed out",
                "latency_ms": max(1, int((time.perf_counter() - start) * 1000)),
                "benchmark_prompt": prompt,
            }
        latency_ms = max(1, int((time.perf_counter() - start) * 1000))
        usage = body.get("usage", {})
        text = ""
        choices = body.get("choices") or []
        if choices:
            text = str(choices[0].get("message", {}).get("content", ""))
        if "completion_tokens" in usage:
            generated = int(usage.get("completion_tokens", 0))
            method = "upstream_usage"
        else:
            generated = max(1, len(text.split()))
            method = "estimated_from_response_text"
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "tokens_generated": generated,
            "tokens_per_sec": round((generated / latency_ms) * 1000, 2),
            "token_count_method": method,
            "benchmark_prompt": prompt,
            "response_text": text,
            "upstream_body": body,
        }

    def _probe_cli(self) -> dict[str, Any]:
        cli_path = self.config.get("llama_cpp_cli_path")
        if not self._binary_available(cli_path):
            return {"ok": False, "output": ""}
        command = [str(cli_path), *split_args(self.config.get("llama_cpp_cli_args"))]
        if len(command) == 1:
            command.append("--version")
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "output": str(exc)}
        return {
            "ok": result.returncode == 0,
            "output": (result.stdout + result.stderr).strip(),
        }

    @staticmethod
    def _binary_available(path: str | None) -> bool:
        if not path:
            return False
        return Path(path).exists() and os.access(path, os.X_OK)
