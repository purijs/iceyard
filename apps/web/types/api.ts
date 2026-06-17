export type UserRead = {
  id: string;
  workspace_id: string;
  username: string;
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
  auth_ref: string | null;
  settings: Record<string, unknown>;
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

export type SnapshotRead = {
  id: string;
  table_id: string;
  snapshot_id: string;
  parent_snapshot_id: string | null;
  operation: string;
  summary: Record<string, unknown>;
  committed_at: string;
};

export type TableRefRead = {
  id: string;
  table_id: string;
  name: string;
  ref_type: string;
  snapshot_id: string;
  retention: Record<string, unknown>;
  is_protected: boolean;
};

export type SchemaVersionRead = {
  id: string;
  table_id: string;
  schema_id: number;
  table_schema: { fields?: Array<Record<string, unknown>> };
  created_at: string;
};

export type PartitionSpecRead = {
  id: string;
  table_id: string;
  spec_id: number;
  spec: Record<string, unknown>;
  is_current: boolean;
};

export type SortOrderRead = {
  id: string;
  table_id: string;
  order_id: number;
  fields: Array<Record<string, unknown>>;
  is_current: boolean;
};

export type TablePreviewRead = {
  resource: string;
  query: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
  rate_limited: boolean;
  masked_columns: string[];
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

export type JobRunRead = {
  id: string;
  job_id: string;
  status: string;
  engine: string;
  compiled_command: string;
  dry_run: boolean;
  pre_op_restore_ref: string | null;
  started_at: string | null;
  ended_at: string | null;
  metrics: Record<string, unknown>;
  error: string | null;
};

export type JobLogRead = {
  id: string;
  job_run_id: string;
  level: string;
  message: string;
  created_at: string;
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

export type RoleRead = {
  id: string;
  workspace_id: string;
  name: string;
  permissions: Array<{ id: string; action: string; resource_selector: Record<string, unknown> }>;
};

export type UserDetailRead = UserRead & {
  roles: Array<{ id: string; name: string }>;
};

export type EditionRead = {
  edition: string;
  features: Record<string, boolean>;
};

export type AutomationPolicy = {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
  selector: Record<string, unknown>;
  trigger: Record<string, unknown>;
  action: { op: string; params: Record<string, unknown> };
  guardrails: Record<string, unknown>;
  alerting: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ClusteringRecommendation = {
  strategy: "sort" | "zorder";
  columns: string[];
  sort_order_expr: string;
  current_clustering_depth: number;
  projected_clustering_depth: number;
  projected_scan_reduction_pct: number;
  apply_operation_id: string;
  apply_params: Record<string, unknown>;
  rationale: string;
};

export type ClusteringAdvice = {
  table_id: string;
  table_name: string;
  workload_basis: string;
  recommendations: ClusteringRecommendation[];
  note: string;
};

export type ParquetAdvice = {
  table_id: string;
  table_name: string;
  current_codec: string;
  recommended_codec: string;
  recommended_level: number;
  dictionary_enabled: boolean;
  row_group_size_bytes: number;
  apply_operation_id: string;
  rationale: string;
  note: string;
};

export type DistributionAdvice = {
  table_id: string;
  table_name: string;
  current_mode: string;
  recommended_mode: string;
  apply_operation_id: string;
  projected_small_file_reduction_pct: number;
  ingestion_hint: string;
  rationale: string;
  note: string;
};

export type CleanupPreview = {
  table_id: string;
  table_name: string;
  cutoff: string;
  partition_aligned: boolean;
  estimated_delete_pct: number;
  estimated_rows_removed: number;
  estimated_bytes_reclaimed: number;
  guardrail_max_delete_pct: number;
  guardrail_passed: boolean;
  mode: string;
  plan: Array<{ name: string; detail: string }>;
  apply_operation_id: string;
  recommend_partitioning: boolean;
  note: string;
};
