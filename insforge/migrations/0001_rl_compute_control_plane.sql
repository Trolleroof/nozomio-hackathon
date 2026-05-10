-- InsForge/Postgres control-plane schema for agent-managed RL/GPU runs.
-- The local test harness mirrors this schema in SQLite so the repo remains
-- usable without live InsForge credentials.

create table if not exists public.rl_experiment_branches (
  name text primary key,
  parent_branch text,
  status text not null check (status in ('active', 'merged', 'abandoned')),
  schema_snapshot jsonb not null default '{}'::jsonb,
  merge_note text,
  created_at timestamptz not null default now(),
  merged_at timestamptz
);

create table if not exists public.rl_environment_contracts (
  id text primary key,
  name text not null,
  version integer not null default 1,
  branch_name text not null references public.rl_experiment_branches(name),
  env_spec jsonb not null,
  observation_schema jsonb not null,
  action_schema jsonb not null,
  reward_spec jsonb not null,
  pass_criteria jsonb not null,
  created_at timestamptz not null default now(),
  unique (name, version, branch_name)
);

create table if not exists public.rl_run_capsules (
  id text primary key,
  user_id text not null,
  env_contract_id text not null references public.rl_environment_contracts(id),
  branch_name text not null references public.rl_experiment_branches(name),
  prompt text not null,
  source_agent text not null default 'agent',
  status text not null check (status in ('approval_required', 'approved', 'running', 'passed', 'failed', 'teardown_verified')),
  provider text,
  provider_offers jsonb not null default '[]'::jsonb,
  cost_estimate jsonb not null default '{}'::jsonb,
  approval_token text,
  logs jsonb not null default '[]'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  audit jsonb not null default '{}'::jsonb,
  model_artifact_uri text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.rl_compute_approvals (
  id text primary key,
  run_id text not null references public.rl_run_capsules(id),
  approved_by text not null,
  provider text not null,
  budget_usd numeric not null check (budget_usd > 0),
  max_runtime_minutes integer not null check (max_runtime_minutes > 0),
  teardown_policy jsonb not null default '{}'::jsonb,
  token text not null unique,
  status text not null check (status in ('signed', 'revoked', 'spent')),
  signed_at timestamptz not null default now()
);

create table if not exists public.rl_compute_memory (
  id text primary key,
  run_id text references public.rl_run_capsules(id),
  provider text not null,
  gpu_name text,
  region text,
  event_type text not null,
  status text not null,
  summary text not null,
  pricing jsonb not null default '{}'::jsonb,
  compatibility jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.rl_training_events (
  id text primary key,
  run_id text not null references public.rl_run_capsules(id),
  channel text not null,
  phase text not null,
  rollout_count integer,
  reward_mean numeric,
  success_rate numeric,
  cost_burn_usd numeric,
  gpu_name text,
  message text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.rl_run_artifacts (
  id text primary key,
  run_id text not null references public.rl_run_capsules(id),
  kind text not null,
  uri text not null,
  storage_bucket text,
  metadata jsonb not null default '{}'::jsonb,
  passed boolean not null default false,
  gpu_name text,
  cost_usd numeric,
  reward_delta numeric,
  success_rate_delta numeric,
  created_at timestamptz not null default now()
);

create index if not exists rl_run_capsules_env_idx on public.rl_run_capsules(env_contract_id);
create index if not exists rl_run_capsules_status_idx on public.rl_run_capsules(status);
create index if not exists rl_compute_memory_provider_idx on public.rl_compute_memory(provider, status);
create index if not exists rl_training_events_run_idx on public.rl_training_events(run_id, created_at);
create index if not exists rl_run_artifacts_passed_idx on public.rl_run_artifacts(passed, cost_usd);

insert into public.rl_experiment_branches (name, parent_branch, status, schema_snapshot)
values ('main', null, 'active', '{}'::jsonb)
on conflict (name) do nothing;

create or replace function public.request_gpu_run(
  run_id text,
  user_id text,
  env_contract_id text,
  branch_name text,
  prompt text,
  source_agent text,
  provider_offers jsonb,
  cost_estimate jsonb
) returns public.rl_run_capsules
language plpgsql
as $$
declare
  created public.rl_run_capsules;
begin
  insert into public.rl_run_capsules (
    id, user_id, env_contract_id, branch_name, prompt, source_agent, status,
    provider_offers, cost_estimate, logs, metrics, audit
  )
  values (
    run_id, user_id, env_contract_id, branch_name, prompt, coalesce(source_agent, 'agent'),
    'approval_required', coalesce(provider_offers, '[]'::jsonb), coalesce(cost_estimate, '{}'::jsonb),
    jsonb_build_array(jsonb_build_object('level', 'info', 'message', 'Signed approval required before paid launch.')),
    '{}'::jsonb,
    jsonb_build_object('passed', false, 'reason', 'not_run')
  )
  returning * into created;
  return created;
end;
$$;

create or replace function public.approve_run(
  approval_id text,
  run_id text,
  approved_by text,
  provider text,
  budget_usd numeric,
  max_runtime_minutes integer,
  teardown_policy jsonb,
  token text
) returns public.rl_compute_approvals
language plpgsql
as $$
declare
  approval public.rl_compute_approvals;
begin
  insert into public.rl_compute_approvals (
    id, run_id, approved_by, provider, budget_usd, max_runtime_minutes,
    teardown_policy, token, status
  )
  values (
    approval_id, run_id, approved_by, provider, budget_usd, max_runtime_minutes,
    coalesce(teardown_policy, '{}'::jsonb), token, 'signed'
  )
  returning * into approval;

  update public.rl_run_capsules
  set status = 'approved', provider = approve_run.provider, approval_token = approve_run.token, updated_at = now()
  where id = approve_run.run_id;

  return approval;
end;
$$;

create or replace function public.mark_teardown_verified(
  run_id text,
  note text default 'Provider teardown verified.'
) returns public.rl_run_capsules
language plpgsql
as $$
declare
  capsule public.rl_run_capsules;
begin
  update public.rl_run_capsules
  set status = 'teardown_verified',
      logs = logs || jsonb_build_array(jsonb_build_object('level', 'info', 'message', note)),
      updated_at = now()
  where id = mark_teardown_verified.run_id
  returning * into capsule;
  return capsule;
end;
$$;

create or replace function public.publish_result(
  artifact_id text,
  run_id text,
  kind text,
  uri text,
  metadata jsonb
) returns public.rl_run_artifacts
language plpgsql
as $$
declare
  artifact public.rl_run_artifacts;
begin
  insert into public.rl_run_artifacts (
    id, run_id, kind, uri, storage_bucket, metadata, passed, gpu_name,
    cost_usd, reward_delta, success_rate_delta
  )
  values (
    artifact_id,
    run_id,
    kind,
    uri,
    'rl-runs',
    coalesce(metadata, '{}'::jsonb),
    coalesce((metadata ->> 'passed')::boolean, false),
    metadata ->> 'gpu_name',
    nullif(metadata ->> 'cost_usd', '')::numeric,
    nullif(metadata ->> 'reward_delta', '')::numeric,
    nullif(metadata ->> 'success_rate_delta', '')::numeric
  )
  returning * into artifact;

  update public.rl_run_capsules
  set status = case when artifact.passed then 'passed' else 'failed' end,
      audit = coalesce(metadata, '{}'::jsonb) || jsonb_build_object('artifact_uri', uri),
      updated_at = now()
  where id = publish_result.run_id;

  return artifact;
end;
$$;

create or replace function public.recommend_next_gpu_run(
  env_contract_id text default null
) returns table (
  recommended_provider text,
  recommended_gpu_name text,
  run_id text,
  artifact_uri text,
  cost_usd numeric,
  success_rate_delta numeric
)
language sql
as $$
  select
    c.provider as recommended_provider,
    a.gpu_name as recommended_gpu_name,
    c.id as run_id,
    a.uri as artifact_uri,
    a.cost_usd,
    a.success_rate_delta
  from public.rl_run_artifacts a
  join public.rl_run_capsules c on c.id = a.run_id
  where a.passed = true
    and (recommend_next_gpu_run.env_contract_id is null or c.env_contract_id = recommend_next_gpu_run.env_contract_id)
  order by coalesce(a.cost_usd, 999999.0) asc, coalesce(a.success_rate_delta, 0) desc, a.created_at desc
  limit 1;
$$;

-- Public MCP credit ledger. Paid provider/API keys remain server-only; public
-- callers receive a small run allowance that the MCP service consumes before
-- spendable work.
create table if not exists public.public_mcp_accounts (
  caller_id text primary key,
  label text,
  credit_limit_runs integer not null default 5 check (credit_limit_runs > 0),
  remaining_runs integer not null default 5 check (remaining_runs >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.public_mcp_usage_events (
  id text primary key,
  caller_id text not null references public.public_mcp_accounts(caller_id),
  tool_name text not null,
  run_count integer not null check (run_count > 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.public_mcp_accounts enable row level security;
alter table public.public_mcp_usage_events enable row level security;

create index if not exists public_mcp_usage_events_caller_created_idx
  on public.public_mcp_usage_events (caller_id, created_at desc);

create or replace function public.claim_public_mcp_credit(
  caller_id text,
  label text default null,
  credit_limit_runs integer default 5
) returns public.public_mcp_accounts
language plpgsql
security definer
as $$
declare
  account public.public_mcp_accounts;
begin
  if caller_id is null or length(trim(caller_id)) = 0 then
    raise exception 'caller_id is required';
  end if;
  if credit_limit_runs <= 0 then
    raise exception 'credit_limit_runs must be positive';
  end if;

  insert into public.public_mcp_accounts (
    caller_id, label, credit_limit_runs, remaining_runs
  )
  values (
    trim(caller_id), label, credit_limit_runs, credit_limit_runs
  )
  on conflict (caller_id) do update set
    label = coalesce(excluded.label, public.public_mcp_accounts.label)
  returning * into account;

  return account;
end;
$$;

create or replace function public.consume_public_mcp_credit(
  event_id text,
  caller_id text,
  tool_name text,
  run_count integer default 1,
  metadata jsonb default '{}'::jsonb,
  credit_limit_runs integer default 5
) returns public.public_mcp_accounts
language plpgsql
security definer
as $$
declare
  account public.public_mcp_accounts;
begin
  account := public.claim_public_mcp_credit(caller_id, null, credit_limit_runs);

  if event_id is null or length(trim(event_id)) = 0 then
    raise exception 'event_id is required';
  end if;
  if tool_name is null or length(trim(tool_name)) = 0 then
    raise exception 'tool_name is required';
  end if;
  if run_count <= 0 then
    raise exception 'run_count must be positive';
  end if;
  if account.remaining_runs < run_count then
    raise exception 'Public MCP credit exhausted';
  end if;

  update public.public_mcp_accounts
  set remaining_runs = remaining_runs - run_count,
      updated_at = now()
  where public_mcp_accounts.caller_id = trim(consume_public_mcp_credit.caller_id)
  returning * into account;

  insert into public.public_mcp_usage_events (
    id, caller_id, tool_name, run_count, metadata
  )
  values (
    event_id,
    trim(caller_id),
    tool_name,
    run_count,
    coalesce(metadata, '{}'::jsonb)
  );

  return account;
end;
$$;
