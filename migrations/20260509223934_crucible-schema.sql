-- Crucible Compute: GPU Deployment Orchestrator Schema

-- Deployment Plans
CREATE TABLE IF NOT EXISTS deployment_plans (
  id TEXT PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  prompt TEXT NOT NULL,
  model_id TEXT NOT NULL,
  objective TEXT NOT NULL,
  provider TEXT NOT NULL,
  accelerator TEXT NOT NULL,
  estimated_hourly_usd DECIMAL(10, 2),
  reason TEXT,
  uncertainty TEXT,
  status TEXT NOT NULL DEFAULT 'draft', -- draft, generated, approved, failed
  approval_required BOOLEAN DEFAULT false,
  approval_reason TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Deployments
CREATE TABLE IF NOT EXISTS deployments (
  id TEXT PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  plan_id TEXT REFERENCES deployment_plans(id),
  name TEXT NOT NULL,
  model_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  accelerator TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft', -- draft, approval_required, approved, queued, provisioning, health_checking, ready, failed, stopping, stopped
  endpoint_url TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Deployment Logs
CREATE TABLE IF NOT EXISTS deployment_logs (
  id TEXT PRIMARY KEY,
  deployment_id TEXT REFERENCES deployments(id) ON DELETE CASCADE,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  level TEXT NOT NULL, -- info, warn, error
  message TEXT NOT NULL
);

-- Health Checks
CREATE TABLE IF NOT EXISTS health_checks (
  id TEXT PRIMARY KEY,
  deployment_id TEXT REFERENCES deployments(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  status TEXT NOT NULL, -- pending, passing, failing, not_run
  latency_ms INTEGER,
  checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Benchmarks
CREATE TABLE IF NOT EXISTS benchmarks (
  id TEXT PRIMARY KEY,
  deployment_id TEXT REFERENCES deployments(id) ON DELETE CASCADE,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  latency_ms INTEGER,
  tokens_per_second DECIMAL(10, 2),
  recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Provider Capabilities
CREATE TABLE IF NOT EXISTS provider_capabilities (
  id TEXT PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  adapter TEXT NOT NULL,
  status TEXT NOT NULL, -- live, dry_run_only, configured, unsupported, failed
  supports_deploy BOOLEAN DEFAULT false,
  supports_logs BOOLEAN DEFAULT false,
  supports_stop BOOLEAN DEFAULT false,
  supports_openai_endpoint BOOLEAN DEFAULT false,
  last_checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_error TEXT,
  notes TEXT,
  UNIQUE(user_id, provider)
);

-- Nia Context Snippets
CREATE TABLE IF NOT EXISTS nia_context_snippets (
  id TEXT PRIMARY KEY,
  deployment_id TEXT REFERENCES deployments(id) ON DELETE CASCADE,
  source TEXT NOT NULL, -- nia://repo/... URIs
  title TEXT NOT NULL,
  excerpt TEXT,
  used_for TEXT,
  searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- API Tokens
CREATE TABLE IF NOT EXISTS api_tokens (
  id TEXT PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  prefix TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_used_at TIMESTAMP WITH TIME ZONE,
  UNIQUE(user_id, prefix)
);

-- Enable RLS on all tables
ALTER TABLE deployment_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployment_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE benchmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE nia_context_snippets ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_tokens ENABLE ROW LEVEL SECURITY;

-- RLS Policies: Users can only see their own data
CREATE POLICY "Users can view own deployment plans" ON deployment_plans FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own deployment plans" ON deployment_plans FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own deployment plans" ON deployment_plans FOR UPDATE TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Users can view own deployments" ON deployments FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own deployments" ON deployments FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own deployments" ON deployments FOR UPDATE TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Users can view own deployment logs" ON deployment_logs FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM deployments d WHERE d.id = deployment_logs.deployment_id AND d.user_id = auth.uid()));
CREATE POLICY "Users can insert own deployment logs" ON deployment_logs FOR INSERT TO authenticated WITH CHECK (EXISTS (SELECT 1 FROM deployments d WHERE d.id = deployment_logs.deployment_id AND d.user_id = auth.uid()));

CREATE POLICY "Users can view own health checks" ON health_checks FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM deployments d WHERE d.id = health_checks.deployment_id AND d.user_id = auth.uid()));

CREATE POLICY "Users can view own benchmarks" ON benchmarks FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM deployments d WHERE d.id = benchmarks.deployment_id AND d.user_id = auth.uid()));

CREATE POLICY "Users can view own provider capabilities" ON provider_capabilities FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own provider capabilities" ON provider_capabilities FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own provider capabilities" ON provider_capabilities FOR UPDATE TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "Users can view own context snippets" ON nia_context_snippets FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM deployments d WHERE d.id = nia_context_snippets.deployment_id AND d.user_id = auth.uid()));

CREATE POLICY "Users can view own API tokens" ON api_tokens FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own API tokens" ON api_tokens FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete own API tokens" ON api_tokens FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- Indexes for performance
CREATE INDEX idx_deployment_plans_user ON deployment_plans(user_id);
CREATE INDEX idx_deployment_plans_status ON deployment_plans(status);
CREATE INDEX idx_deployments_user ON deployments(user_id);
CREATE INDEX idx_deployments_status ON deployments(status);
CREATE INDEX idx_deployments_plan ON deployments(plan_id);
CREATE INDEX idx_deployment_logs_deployment ON deployment_logs(deployment_id);
CREATE INDEX idx_health_checks_deployment ON health_checks(deployment_id);
CREATE INDEX idx_benchmarks_deployment ON benchmarks(deployment_id);
CREATE INDEX idx_provider_capabilities_user ON provider_capabilities(user_id);
CREATE INDEX idx_api_tokens_user ON api_tokens(user_id);
