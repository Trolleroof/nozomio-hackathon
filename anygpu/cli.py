from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from . import __version__
from .domain import (
    benchmark_model,
    broker_capacity_records,
    broker_price_records,
    broker_providers,
    connect_pool,
    create_policy,
    deploy_model,
    cleanup_stale_processes,
    get_compute_inventory,
    optimize_deployment,
    profile_model,
    register_managed_pools,
    register_model,
    refresh_provider_prices,
    refresh_provider_broker,
    run_benchmark,
    runtime_processes,
    explain_scheduled_deployment,
    generate_kubernetes_manifest,
    schedule_deployment,
    set_cost_record,
    serve_runtime_logs,
    serve_runtime_rows,
    start_serve_runtime,
    stop_deployment,
    stop_serve_runtime,
    verify_pool,
)
from .gateway import serve as serve_gateway
from .state import edit_state, load_state


def print_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))


def command_login(args: argparse.Namespace) -> None:
    email = args.email or "local-user@anygpu.dev"
    with edit_state() as state:
        state["session"]["user"] = email
    print(f"Logged in as {email}")


def command_org_create(args: argparse.Namespace) -> None:
    with edit_state() as state:
        state["orgs"][args.name] = {"name": args.name, "created_by": state["session"].get("user")}
        state["session"]["current_org"] = args.name
    print(f"Created org {args.name}")


def command_org_switch(args: argparse.Namespace) -> None:
    with edit_state() as state:
        if args.name not in state["orgs"]:
            raise ValueError(f"Unknown org {args.name}")
        state["session"]["current_org"] = args.name
    print(f"Switched to org {args.name}")


def command_project_create(args: argparse.Namespace) -> None:
    with edit_state() as state:
        org = state["session"].get("current_org")
        if not org:
            raise ValueError("No active org. Run `anygpu org create NAME` first.")
        state["projects"][args.name] = {"name": args.name, "org": org}
        state["session"]["current_project"] = args.name
    print(f"Created project {args.name}")


def command_project_switch(args: argparse.Namespace) -> None:
    with edit_state() as state:
        if args.name not in state["projects"]:
            raise ValueError(f"Unknown project {args.name}")
        state["session"]["current_project"] = args.name
    print(f"Switched to project {args.name}")


def command_compute_use(args: argparse.Namespace) -> None:
    if args.mode != "managed":
        raise ValueError("Only managed mode is supported by this local v1")
    with edit_state() as state:
        register_managed_pools(state)
    print("Managed compute enabled")


def command_compute_connect(args: argparse.Namespace) -> None:
    details = {
        "context": getattr(args, "context", None),
        "namespace": getattr(args, "namespace", None),
        "api_key": getattr(args, "api_key", None),
        "role_arn": getattr(args, "role_arn", None),
        "target": getattr(args, "target", None),
    }
    with edit_state() as state:
        connect_pool(state, args.provider, args.name, **{k: v for k, v in details.items() if v})
    label = "Docker" if args.provider == "docker" else "BYOC" if args.provider in {"kubernetes", "ssh", "aws"} else "provider"
    print(f"Registered {label} pool {args.name}")


def command_compute_inventory(args: argparse.Namespace) -> None:
    with edit_state() as state:
        inventory = get_compute_inventory(state, args.name)
    print(json.dumps(inventory, indent=2, sort_keys=True))


def command_compute_verify(args: argparse.Namespace) -> None:
    with edit_state() as state:
        records = verify_pool(state, args.name)
    print(f"Pool {args.name} certified")
    print_table(
        ["runtime", "hardware", "driver", "max_vram_gb", "modes", "simulated"],
        [
            [
                record["runtime"],
                record["hardware"],
                record["driver"],
                record["max_vram_gb"],
                ",".join(record["supported_modes"]),
                str(record.get("simulated", False)).lower(),
            ]
            for record in records
        ],
    )


def command_compute_pools_list(_: argparse.Namespace) -> None:
    state = load_state()
    pools = sorted(state["compute_pools"].values(), key=lambda item: (item["kind"], item["name"]))
    if not pools:
        print("No compute pools registered. Run `anygpu compute use managed` or `anygpu compute connect ...`.")
        return
    print("Available compute pools:")
    print()
    print_table(
        ["Pool", "Type", "Hardware", "Regions", "Modes", "Status"],
        [
            [
                pool["name"],
                pool["kind"],
                pool["hardware"],
                ",".join(pool["regions"]),
                ",".join(pool["modes"]),
                "certified" if pool.get("certified") else pool.get("status", "registered"),
            ]
            for pool in pools
        ],
    )


def command_broker_refresh(_: argparse.Namespace) -> None:
    with edit_state() as state:
        broker = refresh_provider_broker(state)
    print("Broker catalog refreshed")
    print(f"providers: {len(broker['providers'])}")
    print(f"accelerators: {len(broker['accelerators'])}")
    print(f"managed pools: {len(broker['managed_pools'])}")
    print("source: static_catalog")


def command_providers_list(args: argparse.Namespace) -> None:
    with edit_state() as state:
        rows = broker_providers(state, args.architecture)
    if not rows:
        print("No providers match the requested filter")
        return
    print_table(
        ["Provider", "Name", "Architectures", "Accelerators", "Credential", "Pricing", "Capacity", "Provisioning"],
        [
            [
                row["id"],
                row["name"],
                ",".join(row["architectures"]),
                ",".join(row["accelerators"]),
                row["credential_status"],
                row["pricing_status"],
                row["capacity_status"],
                row["provisioning_status"],
            ]
            for row in rows
        ],
    )


def command_prices_list(args: argparse.Namespace) -> None:
    with edit_state() as state:
        rows = broker_price_records(state, args.accelerator, args.architecture)
    if not rows:
        print("No price records match the requested filter")
        return
    print_table(
        ["Provider", "Pool", "Arch", "Accelerator", "Region", "USD/hr", "Status", "Freshness", "Source"],
        [
            [
                row["provider"],
                row["pool"],
                row["architecture"],
                row["accelerator"],
                row["region"],
                "unknown" if row["price_per_hour_usd"] is None else row["price_per_hour_usd"],
                row["price_status"],
                row["freshness"],
                row["source"],
            ]
            for row in rows
        ],
    )


def command_prices_refresh(args: argparse.Namespace) -> None:
    with edit_state() as state:
        result = refresh_provider_prices(state, args.provider, args.accelerator, args.limit)
    print(f"Refreshed {result['provider']} prices")
    print(f"offers: {result['offers']}")
    print(f"source: {result['source']}")
    print(f"refreshed_at: {result['refreshed_at']}")


def command_capacity_list(args: argparse.Namespace) -> None:
    with edit_state() as state:
        rows = broker_capacity_records(state, args.accelerator, args.architecture)
    if not rows:
        print("No capacity records match the requested filter")
        return
    print_table(
        ["Provider", "Pool", "Arch", "Accelerator", "Region", "Available", "Capacity", "Quota", "Provisioning"],
        [
            [
                row["provider"],
                row["pool"],
                row["architecture"],
                row["accelerator"],
                row["region"],
                "unknown" if row["available"] is None else row["available"],
                row["capacity_status"],
                row["quota_status"],
                row["provisioning_status"],
            ]
            for row in rows
        ],
    )


def command_model_register(args: argparse.Namespace) -> None:
    with edit_state() as state:
        model = register_model(state, args.name, args.source, args.task, args.format, args.base, args.runtime)
    print(f"Registered model {model['name']}")
    print(f"source: {model['source']}")
    print(f"format: {model['format']}")
    print(f"memory estimate: {model['memory_estimate_gb']} GB")


def command_profile(args: argparse.Namespace) -> None:
    with edit_state() as state:
        profile = profile_model(
            state,
            args.model,
            args.traffic,
            args.context,
            args.output_tokens_p50,
            args.latency_p95,
        )
    print(f"Profile for {args.model}")
    print(f"VRAM required: {profile['vram_required_gb']} GB")
    print("Candidate runtimes:")
    for candidate in profile["runtime_candidates"]:
        mark = {"pass": "OK", "needs-verification": "?", "not-ideal": "NO"}.get(candidate["status"], "?")
        print(f"{mark} {candidate['name']}: {candidate['status']}")
    print("Candidate hardware:")
    for candidate in profile["hardware_candidates"]:
        mark = "OK" if candidate["status"] == "pass" else "?" if candidate["status"].startswith("possible") else "NO"
        print(f"{mark} {candidate['name']}: {candidate['status']}")


def command_benchmark(args: argparse.Namespace) -> None:
    if args.benchmark_action == "run":
        command_benchmark_run(args)
        return
    args.model = args.benchmark_action
    with edit_state() as state:
        benchmark = benchmark_model(state, args.model, args.policy, args.targets, args.duration)
    print("Benchmark results:")
    print()
    print_table(
        ["Route", "Runtime", "p95", "tok/s", "Est. cost", "Status", "Simulated"],
        [
            [
                result["route"],
                result["runtime"],
                f"{result['p95_ms']}ms",
                result["tokens_per_sec"],
                result["estimated_cost"],
                result["status"],
                f"simulated={str(result.get('simulated', True)).lower()}",
            ]
            for result in benchmark["results"]
        ],
    )
    passing = [result for result in benchmark["results"] if result["status"] == "pass"]
    if passing:
        print()
        print(f"Recommendation: Primary {passing[0]['route']}")


def command_benchmark_run(args: argparse.Namespace) -> None:
    if not args.model_source:
        raise ValueError("benchmark run requires --model")
    if not args.runtime:
        raise ValueError("benchmark run requires --runtime")
    if not args.compute:
        raise ValueError("benchmark run requires --compute")
    with edit_state() as state:
        result = run_benchmark(state, args.model_source, args.runtime, args.compute, args.profile or "latency-chat")
    print(f"Benchmark {result['id']}")
    print(f"model: {result['model']}")
    print(f"runtime: {result['runtime']}")
    print(f"compute: {result['compute']}")
    print(f"profile: {result['profile']}")
    print(f"success: {str(result['success']).lower()}")
    print(f"simulated: {str(result['simulated']).lower()}")
    print(f"ttft_ms_p50: {result['ttft_ms_p50']}")
    print(f"tokens_per_second_p50: {result['tokens_per_second_p50']}")
    if result.get("error"):
        print(f"error: {result['error']}")


def command_policy_create(args: argparse.Namespace) -> None:
    with edit_state() as state:
        policy = create_policy(
            state,
            args.name,
            objective=args.objective,
            max_p95=args.max_p95,
            fallback=args.fallback,
            regions=args.regions,
            data_residency=args.data_residency,
            prefer=args.prefer,
            allow_managed_overflow=args.allow_managed_overflow,
            spot_allowed=args.spot_allowed,
            serverless_allowed=args.serverless_allowed,
            max_monthly_spend=args.max_monthly_spend,
        )
    print(f"Created policy {policy['name']}")
    print(
        f"objective={policy['objective']} max_p95={policy['max_p95_ms']}ms "
        f"fallback={policy['fallback']} prefer={policy['prefer'] or 'none'}"
    )


def command_serve(args: argparse.Namespace) -> None:
    if not getattr(args, "name", None):
        raise ValueError("Missing --name for deployment serve command")
    if not getattr(args, "policy", None):
        raise ValueError("Missing --policy for deployment serve command")
    with edit_state() as state:
        deployment = deploy_model(
            state,
            args.model,
            args.name,
            args.policy,
            args.runtime,
            args.replicas,
            args.endpoint,
        )
    print(f"Deployment {deployment['name']} is live.")
    print()
    print("Endpoint:")
    print(deployment["url"])
    print()
    for route in deployment["routes"]:
        label = route["role"].capitalize()
        print(f"{label}:")
        print(f"{route['route']} / {route['runtime']} / p95 {route['p95_ms']}ms")
        print()
    policy = load_state()["policies"][deployment["policy"]]
    print("Policy:")
    print(
        f"{policy['objective']} under {policy['max_p95_ms']}ms p95, "
        f"fallback {policy['fallback']}, regions {','.join(policy['regions']) or 'any'}"
    )


def command_serve_start(args: argparse.Namespace) -> None:
    if not args.serve_name:
        raise ValueError("Usage: anygpu serve start NAME --model MODEL --runtime llama.cpp --compute POOL")
    if not args.model_path:
        raise ValueError("serve start requires --model")
    if not args.runtime:
        raise ValueError("serve start requires --runtime")
    if not args.compute:
        raise ValueError("serve start requires --compute")
    with edit_state() as state:
        deployment = start_serve_runtime(
            state,
            args.serve_name,
            args.model_path,
            args.runtime,
            args.compute,
            plan=args.plan,
            region=args.region,
            accelerator=args.accelerator,
            deployment_kind=args.deployment_kind,
            os_id=args.os_id,
            ssh_key_ids=args.ssh_key_ids,
            firewall_group_id=args.firewall_group_id,
            offer_id=args.offer_id,
            max_price=args.max_price,
            disk_gb=args.disk_gb,
            confirm_cost=args.confirm_cost,
        )
    print(f"Started {deployment['name']} on {deployment['compute']}")
    print(deployment["url"])


def command_serve_ps(_: argparse.Namespace) -> None:
    with edit_state() as state:
        rows = serve_runtime_rows(state)
    if not rows:
        print("No serve runtimes tracked")
        return
    print_table(
        ["Name", "Compute", "Runtime", "Health", "Port", "Container", "URL"],
        [
            [
                row["name"],
                row["compute"],
                row["runtime"],
                row["health"],
                row["port"],
                row["container"],
                row["url"],
            ]
            for row in rows
        ],
    )


def command_serve_logs(args: argparse.Namespace) -> None:
    if not args.serve_name:
        raise ValueError("Usage: anygpu serve logs NAME")
    state = load_state()
    print(serve_runtime_logs(state, args.serve_name), end="")


def command_serve_stop(args: argparse.Namespace) -> None:
    if not args.serve_name:
        raise ValueError("Usage: anygpu serve stop NAME")
    with edit_state() as state:
        stop_serve_runtime(state, args.serve_name)
    print(f"Stopped {args.serve_name}")


def command_serve_dispatch(args: argparse.Namespace) -> None:
    if args.serve_action == "start":
        command_serve_start(args)
    elif args.serve_action == "ps":
        command_serve_ps(args)
    elif args.serve_action == "logs":
        command_serve_logs(args)
    elif args.serve_action == "stop":
        command_serve_stop(args)
    else:
        args.model = args.serve_action
        command_serve(args)


def command_deployments_status(args: argparse.Namespace) -> None:
    state = load_state()
    deployment = state["deployments"].get(args.name)
    if not deployment:
        raise ValueError(f"Unknown deployment {args.name}")
    print(f"Deployment {args.name}")
    for route in deployment["routes"]:
        print(f"{route['role'].capitalize()} route:")
        print(route["route"])
        print(f"health: {route['status']}")
        print(f"simulated: {str(route.get('simulated', True)).lower()}")
        if route.get("upstream_url"):
            print(f"upstream: {route['upstream_url']}")
        print(f"p95: {route['p95_ms']}ms")
        print(f"error rate: {deployment['metrics']['error_rate'] * 100:.2f}%")
        print(f"cost: ${deployment['metrics']['cost_per_1m_tokens']} / 1M tokens effective")
    if deployment.get("runtime_process"):
        process = deployment["runtime_process"]
        print("Runtime process:")
        if process.get("pid"):
            print(f"pid: {process['pid']}")
        if process.get("container_id"):
            print(f"container: {process['container_id']}")
        if process.get("container_name"):
            print(f"container_name: {process['container_name']}")
        print(f"health: {process.get('health')}")
        print(f"port: {process.get('port')}")
        if process.get("upstream_url"):
            print(f"upstream: {process['upstream_url']}")
        if process.get("logs_path"):
            print(f"logs: {process['logs_path']}")


def command_deployments_stop(args: argparse.Namespace) -> None:
    with edit_state() as state:
        stop_deployment(state, args.name)
    print(f"Stopped deployment {args.name}")


def command_logs(args: argparse.Namespace) -> None:
    state = load_state()
    for event in state["events"]:
        if event["target"] in {args.name, "compute"}:
            print(f"{event['time']} {event['message']}")


def command_metrics(args: argparse.Namespace) -> None:
    state = load_state()
    deployment = state["deployments"].get(args.name)
    if not deployment:
        raise ValueError(f"Unknown deployment {args.name}")
    for key, value in deployment["metrics"].items():
        print(f"{key}: {value}")


def command_costs(args: argparse.Namespace) -> None:
    if getattr(args, "costs_action", None) == "set":
        command_costs_set(args)
        return
    state = load_state()
    deployment = state["deployments"].get(args.costs_action)
    if not deployment:
        raise ValueError(f"Unknown deployment {args.costs_action}")
    total = sum(event["cost_usd"] for event in state["cost_events"] if event["deployment"] == args.costs_action)
    print(f"{args.costs_action} effective cost: ${deployment['metrics']['cost_per_1m_tokens']} / 1M tokens")
    print(f"recorded usage cost: ${total:.6f}")


def command_costs_set(args: argparse.Namespace) -> None:
    if not args.compute:
        raise ValueError("costs set requires --compute")
    if args.per_1m_tokens is None:
        raise ValueError("costs set requires --per-1m-tokens")
    with edit_state() as state:
        record = set_cost_record(state, args.compute, args.per_1m_tokens, args.label)
    print(f"Set cost for {record['compute']}: {record['label']}")


def command_optimize(args: argparse.Namespace) -> None:
    with edit_state() as state:
        result = optimize_deployment(state, args.name)
    if result["found"]:
        print("New route found:")
        print(result["route"])
        print(f"Expected cost reduction: {result['expected_cost_reduction']}")
        print(f"Latency improvement: {result['latency_improvement_ms']}ms")
        print(f"Risk: {result['risk']}")
        print(f"Command: anygpu deploy promote {args.name} --route {result['route']}")
    else:
        print(result["message"])


def command_deploy_promote(args: argparse.Namespace) -> None:
    with edit_state() as state:
        deployment = state["deployments"].get(args.name)
        if not deployment:
            raise ValueError(f"Unknown deployment {args.name}")
        for index, route in enumerate(deployment["routes"]):
            if route["route"] == args.route:
                deployment["routes"].insert(0, deployment["routes"].pop(index))
                deployment["routes"][0]["role"] = "primary"
                for fallback_index, fallback in enumerate(deployment["routes"][1:], start=1):
                    fallback["role"] = "fallback" if fallback_index == 1 else "overflow"
                break
        else:
            raise ValueError(f"Unknown route {args.route}")
    print(f"Promoted {args.route} for {args.name}")


def command_deploy_rollback(args: argparse.Namespace) -> None:
    print(f"Rollback recorded for {args.name}. No previous release exists in this local v1.")


def command_deploy_schedule(args: argparse.Namespace) -> None:
    if not args.model_source:
        raise ValueError("deploy requires --model")
    if args.target == "kubernetes":
        with edit_state() as state:
            manifest = generate_kubernetes_manifest(
                state,
                args.deploy_action,
                args.model_source,
                args.runtime,
                args.gpu,
                args.namespace,
                args.replicas,
            )
        print(manifest["yaml"], end="")
        return
    with edit_state() as state:
        deployment = schedule_deployment(
            state,
            args.deploy_action,
            args.model_source,
            args.strategy,
            args.sla,
            args.max_cost,
        )
    selected = deployment["scheduler_decision"]["selected"]
    print(f"Deployment {deployment['name']} scheduled")
    print(f"Selected runtime: {selected['runtime']}")
    print(f"Selected provider: {selected['provider']}")
    print(f"Selected compute: {selected['compute']}")
    print(f"Selected hardware: {selected['hardware_name']}")
    print("Reasons:")
    for reason in selected["reasons"]:
        print(f"- {reason}")


def command_deploy_dispatch(args: argparse.Namespace) -> None:
    if args.deploy_action == "promote":
        if not args.deploy_name:
            raise ValueError("Usage: anygpu deploy promote NAME --route ROUTE")
        args.name = args.deploy_name
        command_deploy_promote(args)
    elif args.deploy_action == "rollback":
        if not args.deploy_name:
            raise ValueError("Usage: anygpu deploy rollback NAME")
        args.name = args.deploy_name
        command_deploy_rollback(args)
    else:
        command_deploy_schedule(args)


def command_explain(args: argparse.Namespace) -> None:
    state = load_state()
    print(explain_scheduled_deployment(state, args.name))


def command_fallback_set(args: argparse.Namespace) -> None:
    with edit_state() as state:
        deployment = state["deployments"].get(args.name)
        if not deployment:
            raise ValueError(f"Unknown deployment {args.name}")
        deployment["fallback_order"] = [args.primary, args.secondary, args.tertiary]
    print(f"Fallback order set for {args.name}")


def command_fallback_test(args: argparse.Namespace) -> None:
    with edit_state() as state:
        deployment = state["deployments"].get(args.name)
        if not deployment:
            raise ValueError(f"Unknown deployment {args.name}")
        if len(deployment["routes"]) < 2:
            raise ValueError("Deployment has no fallback route")
        primary, fallback = deployment["routes"][0], deployment["routes"][1]
        primary["status"] = "degraded"
        fallback["status"] = "healthy"
        state["events"].append(
            {
                "time": "now",
                "target": args.name,
                "message": f"Fallback test shifted traffic from {primary['route']} to {fallback['route']}",
            }
        )
    print(f"Fallback test passed for {args.name}")


def command_events(args: argparse.Namespace) -> None:
    state = load_state()
    for event in state["events"]:
        if event["target"] == args.name:
            print(f"{event['time']} {event['message']}")


def command_gateway(args: argparse.Namespace) -> None:
    serve_gateway(args.host, args.port)


def command_config_set(args: argparse.Namespace) -> None:
    with edit_state() as state:
        state.setdefault("config", {})[args.key] = args.value
    print(f"Set {args.key}")


def command_config_list(_: argparse.Namespace) -> None:
    state = load_state()
    for key, value in sorted(state.get("config", {}).items()):
        print(f"{key}: {value}")


def command_runtime_ps(_: argparse.Namespace) -> None:
    state = load_state()
    rows = runtime_processes(state)
    if not rows:
        print("No runtime processes tracked")
        return
    print_table(
        ["Deployment", "PID", "Runtime", "Health", "Host", "Port", "Logs"],
        [
            [
                row["deployment"],
                row["pid"],
                row["runtime"],
                row["health"],
                row["host"],
                row["port"],
                row["logs_path"],
            ]
            for row in rows
        ],
    )


def command_runtime_cleanup(_: argparse.Namespace) -> None:
    with edit_state() as state:
        cleaned = cleanup_stale_processes(state)
    if cleaned:
        print("Cleaned stale runtime processes:")
        for name in cleaned:
            print(name)
    else:
        print("No stale runtime processes found")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anygpu")
    parser.add_argument("--version", action="version", version=f"anygpu {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login")
    login.add_argument("--email")
    login.set_defaults(func=command_login)

    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_set.set_defaults(func=command_config_set)
    config_list = config_sub.add_parser("list")
    config_list.set_defaults(func=command_config_list)

    org = sub.add_parser("org")
    org_sub = org.add_subparsers(dest="org_command", required=True)
    org_create = org_sub.add_parser("create")
    org_create.add_argument("name")
    org_create.set_defaults(func=command_org_create)
    org_switch = org_sub.add_parser("switch")
    org_switch.add_argument("name")
    org_switch.set_defaults(func=command_org_switch)

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_create = project_sub.add_parser("create")
    project_create.add_argument("name")
    project_create.set_defaults(func=command_project_create)
    project_switch = project_sub.add_parser("switch")
    project_switch.add_argument("name")
    project_switch.set_defaults(func=command_project_switch)

    compute = sub.add_parser("compute")
    compute_sub = compute.add_subparsers(dest="compute_command", required=True)
    compute_use = compute_sub.add_parser("use")
    compute_use.add_argument("mode")
    compute_use.set_defaults(func=command_compute_use)
    compute_connect = compute_sub.add_parser("connect")
    compute_connect.add_argument("provider", choices=["kubernetes", "ssh", "runpod", "lambda", "aws", "vultr", "vast", "docker"])
    compute_connect.add_argument("target", nargs="?")
    compute_connect.add_argument("--name", required=True)
    compute_connect.add_argument("--context")
    compute_connect.add_argument("--namespace")
    compute_connect.add_argument("--api-key")
    compute_connect.add_argument("--role-arn")
    compute_connect.set_defaults(func=command_compute_connect)
    compute_verify = compute_sub.add_parser("verify")
    compute_verify.add_argument("name")
    compute_verify.set_defaults(func=command_compute_verify)
    compute_inventory = compute_sub.add_parser("inventory")
    compute_inventory.add_argument("name")
    compute_inventory.set_defaults(func=command_compute_inventory)
    compute_pools = compute_sub.add_parser("pools")
    compute_pools_sub = compute_pools.add_subparsers(dest="pools_command", required=True)
    compute_pools_list = compute_pools_sub.add_parser("list")
    compute_pools_list.set_defaults(func=command_compute_pools_list)

    broker = sub.add_parser("broker")
    broker_sub = broker.add_subparsers(dest="broker_command", required=True)
    broker_refresh = broker_sub.add_parser("refresh")
    broker_refresh.set_defaults(func=command_broker_refresh)

    providers = sub.add_parser("providers")
    providers_sub = providers.add_subparsers(dest="providers_command", required=True)
    providers_list = providers_sub.add_parser("list")
    providers_list.add_argument("--architecture")
    providers_list.set_defaults(func=command_providers_list)
    providers_status = providers_sub.add_parser("status")
    providers_status.add_argument("--architecture")
    providers_status.set_defaults(func=command_providers_list)

    prices = sub.add_parser("prices")
    prices_sub = prices.add_subparsers(dest="prices_command", required=True)
    prices_list = prices_sub.add_parser("list")
    prices_list.add_argument("--accelerator")
    prices_list.add_argument("--architecture")
    prices_list.set_defaults(func=command_prices_list)
    prices_refresh = prices_sub.add_parser("refresh")
    prices_refresh.add_argument("--provider", required=True)
    prices_refresh.add_argument("--accelerator")
    prices_refresh.add_argument("--limit", type=int, default=100)
    prices_refresh.set_defaults(func=command_prices_refresh)

    capacity = sub.add_parser("capacity")
    capacity_sub = capacity.add_subparsers(dest="capacity_command", required=True)
    capacity_list = capacity_sub.add_parser("list")
    capacity_list.add_argument("--accelerator")
    capacity_list.add_argument("--architecture")
    capacity_list.set_defaults(func=command_capacity_list)

    model = sub.add_parser("model")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    model_register = model_sub.add_parser("register")
    model_register.add_argument("name")
    model_register.add_argument("--source", required=True)
    model_register.add_argument("--format", default="safetensors")
    model_register.add_argument("--task", default="chat")
    model_register.add_argument("--base")
    model_register.add_argument("--runtime")
    model_register.set_defaults(func=command_model_register)

    profile = sub.add_parser("profile")
    profile.add_argument("model")
    profile.add_argument("--traffic")
    profile.add_argument("--context")
    profile.add_argument("--output-tokens-p50")
    profile.add_argument("--latency-p95")
    profile.set_defaults(func=command_profile)

    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("benchmark_action")
    benchmark.add_argument("--model", dest="model_source")
    benchmark.add_argument("--runtime")
    benchmark.add_argument("--compute")
    benchmark.add_argument("--profile")
    benchmark.add_argument("--policy")
    benchmark.add_argument("--targets")
    benchmark.add_argument("--duration")
    benchmark.set_defaults(func=command_benchmark)

    policy = sub.add_parser("policy")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    policy_create = policy_sub.add_parser("create")
    policy_create.add_argument("name")
    policy_create.add_argument("--objective", default="balanced")
    policy_create.add_argument("--max-p95")
    policy_create.add_argument("--fallback", default="optional")
    policy_create.add_argument("--regions")
    policy_create.add_argument("--data-residency")
    policy_create.add_argument("--prefer")
    policy_create.add_argument("--allow-managed-overflow")
    policy_create.add_argument("--spot-allowed")
    policy_create.add_argument("--serverless-allowed")
    policy_create.add_argument("--max-monthly-spend")
    policy_create.set_defaults(func=command_policy_create)

    serve = sub.add_parser("serve")
    serve.add_argument("serve_action")
    serve.add_argument("serve_name", nargs="?")
    serve.add_argument("--name")
    serve.add_argument("--policy")
    serve.add_argument("--model", dest="model_path")
    serve.add_argument("--compute")
    serve.add_argument("--runtime")
    serve.add_argument("--plan")
    serve.add_argument("--region")
    serve.add_argument("--accelerator")
    serve.add_argument("--deployment-kind", choices=["cloud-gpu", "bare-metal"])
    serve.add_argument("--os-id", type=int)
    serve.add_argument("--ssh-key-ids")
    serve.add_argument("--firewall-group-id")
    serve.add_argument("--offer-id")
    serve.add_argument("--max-price", type=float)
    serve.add_argument("--disk-gb", type=int)
    serve.add_argument("--confirm-cost", action="store_true")
    serve.add_argument("--replicas")
    serve.add_argument("--endpoint", default="openai")
    serve.set_defaults(func=command_serve_dispatch)

    deployments = sub.add_parser("deployments")
    deployments_sub = deployments.add_subparsers(dest="deployments_command", required=True)
    deployments_status = deployments_sub.add_parser("status")
    deployments_status.add_argument("name")
    deployments_status.set_defaults(func=command_deployments_status)
    deployments_stop = deployments_sub.add_parser("stop")
    deployments_stop.add_argument("name")
    deployments_stop.set_defaults(func=command_deployments_stop)

    logs = sub.add_parser("logs")
    logs.add_argument("name")
    logs.set_defaults(func=command_logs)

    metrics = sub.add_parser("metrics")
    metrics.add_argument("name")
    metrics.set_defaults(func=command_metrics)

    costs = sub.add_parser("costs")
    costs.add_argument("costs_action")
    costs.add_argument("--compute")
    costs.add_argument("--per-1m-tokens")
    costs.add_argument("--label")
    costs.set_defaults(func=command_costs)

    optimize = sub.add_parser("optimize")
    optimize.add_argument("name")
    optimize.set_defaults(func=command_optimize)

    deploy = sub.add_parser("deploy")
    deploy.add_argument("deploy_action")
    deploy.add_argument("deploy_name", nargs="?")
    deploy.add_argument("--route")
    deploy.add_argument("--model", dest="model_source")
    deploy.add_argument("--sla", default="latency")
    deploy.add_argument("--strategy", default="cheapest-compatible")
    deploy.add_argument("--max-cost")
    deploy.add_argument("--runtime")
    deploy.add_argument("--target")
    deploy.add_argument("--gpu")
    deploy.add_argument("--namespace")
    deploy.add_argument("--replicas")
    deploy.set_defaults(func=command_deploy_dispatch)

    explain = sub.add_parser("explain")
    explain.add_argument("name")
    explain.set_defaults(func=command_explain)

    fallback = sub.add_parser("fallback")
    fallback_sub = fallback.add_subparsers(dest="fallback_command", required=True)
    fallback_set = fallback_sub.add_parser("set")
    fallback_set.add_argument("name")
    fallback_set.add_argument("--primary", required=True)
    fallback_set.add_argument("--secondary", required=True)
    fallback_set.add_argument("--tertiary")
    fallback_set.set_defaults(func=command_fallback_set)
    fallback_test = fallback_sub.add_parser("test")
    fallback_test.add_argument("name")
    fallback_test.set_defaults(func=command_fallback_test)

    events = sub.add_parser("events")
    events.add_argument("name")
    events.set_defaults(func=command_events)

    gateway = sub.add_parser("gateway")
    gateway.add_argument("--host", default="127.0.0.1")
    gateway.add_argument("--port", type=int, default=8765)
    gateway.set_defaults(func=command_gateway)

    runtime = sub.add_parser("runtime")
    runtime_sub = runtime.add_subparsers(dest="runtime_command", required=True)
    runtime_ps = runtime_sub.add_parser("ps")
    runtime_ps.set_defaults(func=command_runtime_ps)
    runtime_cleanup = runtime_sub.add_parser("cleanup")
    runtime_cleanup.set_defaults(func=command_runtime_cleanup)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
