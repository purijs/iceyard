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
  workspace_id: string;
  namespace_id: string;
  catalog_connection_id: string | null;
  environment_id: string;
  name: string;
  location: string;
  format_version: number;
  current_snapshot_id: string | null;
  table_uuid: string | null;
  metadata_location: string | null;
  previous_metadata_location: string | null;
  last_sequence_number: number | null;
  last_updated_at: string | null;
  current_schema_id: number | null;
  default_spec_id: number | null;
  default_sort_order_id: number | null;
  record_count: number | null;
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

export type ObjectStoreConnectionRead = {
  id: string;
  environment_id: string;
  name: string;
  store_type: "s3" | "gcs" | "adls" | "hdfs" | "local";
  endpoint: string | null;
  region: string | null;
  auth_ref: string | null;
  settings: Record<string, unknown>;
};

export type ConnectionTestResult = {
  connection_id: string;
  status: "ok" | "warning" | "failed";
  message: string;
  capabilities: Record<string, unknown>;
  components: Array<{
    name: string;
    status: "ok" | "warning" | "failed";
    message: string;
  }>;
};

export type ComputeBackendRead = {
  id: string;
  environment_id: string;
  name: string;
  backend_type: "embedded" | "spark" | "trino" | "flink" | "duckdb" | "custom";
  settings: Record<string, unknown>;
  is_enabled: boolean;
  created_at: string;
};

export type TableIndexRefreshResult = {
  catalog_connection_id: string | null;
  namespace_count: number;
  table_count: number;
  discovered_table_count: number;
  removed_table_count: number;
  parsed_table_count: number;
  skipped_table_count: number;
  failed_table_count: number;
  mode: string;
  sync_run_id: string | null;
  refreshed_at: string;
  errors: Array<{ table?: string; error: string }>;
  worker_count: number;
  parse_job_count: number;
};

export type MetadataSyncRunRead = {
  id: string;
  workspace_id: string;
  catalog_connection_id: string;
  status: string;
  mode: string;
  started_at: string;
  finished_at: string | null;
  table_count: number;
  discovered_table_count: number;
  removed_table_count: number;
  parsed_table_count: number;
  skipped_table_count: number;
  failed_table_count: number;
  error: string | null;
  stats: Record<string, unknown>;
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
  docs_url: string | null;
  scope: "catalog" | "namespace" | "table" | "none" | "governance" | "maintenance" | "migration";
  requires_table: boolean;
  requires_catalog: boolean;
  writes_data: boolean;
  writes_metadata: boolean;
  native_metadata: boolean;
  native_preview: boolean;
  spark_required: boolean;
  trino_supported: boolean;
  flink_supported: boolean;
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

export type TableMetadataRead = {
  table: TableRead;
  snapshots: SnapshotRead[];
  refs: TableRefRead[];
  schemas: SchemaVersionRead[];
  partitions: PartitionSpecRead[];
  sort_orders: SortOrderRead[];
  metadata_log: Array<Record<string, unknown>>;
  snapshot_log: Array<Record<string, unknown>>;
  metrics: TableMetricsRead | null;
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
  operation_id: string | null;
  table_id: string | null;
  table_name: string | null;
  environment_id: string | null;
  catalog_connection_id: string | null;
  kind: string;
  status: string;
  correlation_id: string | null;
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
  workspace_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  occurred_at: string;
  event_metadata: Record<string, unknown>;
};

export type ApprovalRead = {
  id: string;
  workspace_id: string;
  operation_request_id: string;
  requested_by: string | null;
  reviewer_id: string | null;
  status: string;
  reason: string | null;
  compiled_command_snapshot: string;
  created_at: string;
  reviewed_at: string | null;
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
