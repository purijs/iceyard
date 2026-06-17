export type UserRead = {
  id: string;
  workspace_id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_service_account: boolean;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
};

export type BootstrapResponse = {
  workspace_id: string;
  user: UserRead;
  token: TokenResponse;
};

export type DashboardRead = {
  table_count: number;
  average_health: number;
  needs_attention: number;
  active_jobs: number;
  storage_bytes: number;
  top_risks: Array<Record<string, unknown>>;
};

export type TableMetricsRead = {
  file_count: number;
  data_size_bytes: number;
  delete_file_count: number;
  snapshot_count: number;
  manifest_count: number;
  small_file_ratio: number;
  last_commit_at: string | null;
  last_compaction_at: string | null;
};

export type TableRead = {
  id: string;
  namespace_id: string;
  environment_id: string;
  name: string;
  location: string;
  format_version: number;
  current_snapshot_id: string | null;
  owner: string | null;
  properties: Record<string, unknown>;
  health_score: number;
  indexed_at: string;
  metrics: TableMetricsRead | null;
};

export type HealthRead = {
  table_id: string;
  score: number;
  severity: "healthy" | "warning" | "critical" | "unknown";
  dimensions: Array<{ name: string; weight: number; score: number; details: Record<string, unknown> }>;
  findings: Array<{ severity: string; message: string; operation_ids: string[] }>;
  recommended_actions: string[];
};

export type CatalogConnectionRead = {
  id: string;
  environment_id: string;
  name: string;
  catalog_type: string;
  endpoint: string | null;
  warehouse: string | null;
  capabilities: Record<string, unknown>;
  is_enabled: boolean;
  last_tested_at: string | null;
};

export type EnvironmentRead = {
  id: string;
  name: string;
  kind: string;
  region: string | null;
  posture: Record<string, unknown>;
};

export type OperationDescriptor = {
  id: string;
  name: string;
  description: string;
  category: string;
  safety_class: "READ" | "METADATA" | "WRITE" | "REWRITE" | "DESTRUCTIVE" | "MIGRATION_ADMIN";
  supported_engines: string[];
  required_permissions: string[];
  params: Array<{
    name: string;
    type: string;
    required: boolean;
    default: unknown;
    options: string[] | null;
    placeholder: string | null;
    advanced: boolean;
    show_if: Record<string, unknown> | null;
  }>;
  sql_template: string;
  dry_run_supported: boolean;
  approval_required: boolean;
  restore_point_required: boolean;
  gates: string[];
};

export type OperationCategoryRead = {
  name: string;
  operation_count: number;
  safety_classes: OperationDescriptor["safety_class"][];
};

export type OperationDryRunRead = {
  id: string;
  operation_id: string;
  table_id: string | null;
  compiled_command: string;
  safety_class: OperationDescriptor["safety_class"];
  gate_results: Array<{ id: string; label: string; status: "passed" | "blocked" | "pending"; detail: string }>;
  metrics: Record<string, unknown>;
  created_at: string;
};

export type OperationExecuteRead = {
  status: "queued" | "requires_approval" | "blocked";
  message: string;
  job_id: string | null;
  approval_request_id: string | null;
};

export type JobRead = {
  id: string;
  operation_request_id: string | null;
  kind: string;
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type AuditEventRead = {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_id: string | null;
  occurred_at: string;
  event_metadata: Record<string, unknown>;
};
