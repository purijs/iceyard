import type {
  AuditEventRead,
  AutomationPolicy,
  ApprovalRead,
  BootstrapResponse,
  CatalogConnectionRead,
  ComputeBackendRead,
  ConnectionTestResult,
  CleanupPreview,
  ClusteringAdvice,
  DashboardRead,
  DistributionAdvice,
  EditionRead,
  EnvironmentRead,
  HealthRead,
  MetadataSyncRunRead,
  ParquetAdvice,
  JobLogRead,
  JobRead,
  JobRunRead,
  ObjectStoreConnectionRead,
  OperationCategoryRead,
  OperationDescriptor,
  OperationDryRunRead,
  OperationExecuteRead,
  PartitionSpecRead,
  RoleRead,
  SchemaVersionRead,
  SnapshotRead,
  SortOrderRead,
  TablePreviewRead,
  TableIndexRefreshResult,
  TableMetadataRead,
  TableRead,
  TableRefRead,
  TokenResponse,
  UserDetailRead,
  UserRead
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("content-type", "application/json");
  if (token) {
    headers.set("authorization", `Bearer ${token}`);
  }
  // Double-submit CSRF token for cookie-authenticated, state-changing requests.
  const method = (options.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    const csrf = readCookie("iceyard_csrf");
    if (csrf) {
      headers.set("x-csrf-token", csrf);
    }
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include"
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail ?? message;
    } catch {
      message = response.statusText;
    }
    throw new Error(message);
  }
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  bootstrap: (body: { workspace_name: string; email: string; password: string; display_name: string }) =>
    request<BootstrapResponse>("/api/v1/auth/bootstrap", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { username: string; password: string }) =>
    request<TokenResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: (token: string) => request<UserRead>("/api/v1/auth/me", {}, token),
  changePassword: (token: string, body: { current_password: string; new_password: string }) =>
    request<{ status: string }>("/api/v1/auth/password", { method: "POST", body: JSON.stringify(body) }, token),
  logout: (token: string) =>
    request<{ status: string }>("/api/v1/auth/logout", { method: "POST", body: JSON.stringify({}) }, token),
  users: (token: string) => request<UserDetailRead[]>("/api/v1/users", {}, token),
  roles: (token: string) => request<RoleRead[]>("/api/v1/roles", {}, token),
  createUser: (token: string, body: { username: string; password: string; role_ids: string[] }) =>
    request<UserDetailRead>("/api/v1/users", { method: "POST", body: JSON.stringify(body) }, token),
  updateUser: (token: string, userId: string, body: { role_ids?: string[]; is_active?: boolean }) =>
    request<UserDetailRead>(`/api/v1/users/${userId}`, { method: "PATCH", body: JSON.stringify(body) }, token),
  dashboard: (token: string) => request<DashboardRead>("/api/v1/dashboard", {}, token),
  tables: (
    token: string,
    filters: { environmentId?: string | null; catalogConnectionId?: string | null } = {}
  ) => {
    const params = new URLSearchParams();
    if (filters.environmentId) params.set("environment_id", filters.environmentId);
    if (filters.catalogConnectionId) params.set("catalog_connection_id", filters.catalogConnectionId);
    const query = params.toString();
    return request<TableRead[]>(`/api/v1/tables${query ? `?${query}` : ""}`, {}, token);
  },
  tableHealth: (token: string, tableId: string) => request<HealthRead>(`/api/v1/tables/${tableId}/health`, {}, token),
  tableSnapshots: (token: string, tableId: string) =>
    request<SnapshotRead[]>(`/api/v1/tables/${tableId}/snapshots`, {}, token),
  tableRefs: (token: string, tableId: string) =>
    request<TableRefRead[]>(`/api/v1/tables/${tableId}/refs`, {}, token),
  tableSchema: (token: string, tableId: string) =>
    request<SchemaVersionRead[]>(`/api/v1/tables/${tableId}/schema`, {}, token),
  tablePartitions: (token: string, tableId: string) =>
    request<PartitionSpecRead[]>(`/api/v1/tables/${tableId}/partitions`, {}, token),
  tableSortOrders: (token: string, tableId: string) =>
    request<SortOrderRead[]>(`/api/v1/tables/${tableId}/sort-orders`, {}, token),
  tableMetadata: (token: string, tableId: string) =>
    request<TableMetadataRead>(`/api/v1/tables/${tableId}/metadata`, {}, token),
  tablePreview: (token: string, tableId: string, resource = "rows") =>
    request<TablePreviewRead>(`/api/v1/tables/${tableId}/preview?resource=${encodeURIComponent(resource)}`, {}, token),
  rowPreview: (
    token: string,
    tableId: string,
    body: { limit?: number; selected_fields?: string[]; snapshot_id?: number | null }
  ) =>
    request<TablePreviewRead>(
      `/api/v1/tables/${tableId}/row-preview`,
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  refreshTableIndex: (token: string, body: { catalog_connection_id?: string | null; force?: boolean }) =>
    request<TableIndexRefreshResult>(
      "/api/v1/tables/index/refresh",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  syncCatalogMetadata: (token: string, catalogConnectionId: string, body: { force?: boolean } = {}) =>
    request<TableIndexRefreshResult>(
      `/api/v1/catalogs/${catalogConnectionId}/sync`,
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  syncRuns: (token: string, catalogConnectionId?: string | null) => {
    const params = new URLSearchParams();
    if (catalogConnectionId) params.set("catalog_connection_id", catalogConnectionId);
    const query = params.toString();
    return request<MetadataSyncRunRead[]>(`/api/v1/tables/sync-runs${query ? `?${query}` : ""}`, {}, token);
  },
  syncRun: (token: string, syncRunId: string) =>
    request<MetadataSyncRunRead>(`/api/v1/tables/sync-runs/${syncRunId}`, {}, token),
  catalogDatabaseSchema: (token: string, catalogConnectionId: string) =>
    request<Record<string, unknown>>(`/api/v1/catalogs/${catalogConnectionId}/database-schema`, {}, token),
  environments: (token: string) => request<EnvironmentRead[]>("/api/v1/environments", {}, token),
  connections: (token: string) => request<CatalogConnectionRead[]>("/api/v1/connections/catalogs", {}, token),
  objectStores: (token: string) =>
    request<ObjectStoreConnectionRead[]>("/api/v1/connections/object-stores", {}, token),
  computeBackends: (token: string) =>
    request<ComputeBackendRead[]>("/api/v1/connections/compute-backends", {}, token),
  createComputeBackend: (
    token: string,
    body: {
      environment_id: string;
      name: string;
      backend_type: ComputeBackendRead["backend_type"];
      settings?: Record<string, unknown>;
    }
  ) =>
    request<ComputeBackendRead>(
      "/api/v1/connections/compute-backends",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  updateComputeBackend: (
    token: string,
    backendId: string,
    body: {
      environment_id?: string;
      name?: string;
      backend_type?: ComputeBackendRead["backend_type"];
      settings?: Record<string, unknown>;
      is_enabled?: boolean;
    }
  ) =>
    request<ComputeBackendRead>(
      `/api/v1/connections/compute-backends/${backendId}`,
      { method: "PATCH", body: JSON.stringify(body) },
      token
    ),
  deleteComputeBackend: (token: string, backendId: string) =>
    request<void>(`/api/v1/connections/compute-backends/${backendId}`, { method: "DELETE" }, token),
  createEnvironment: (token: string, body: { name: string; kind: string; region?: string; posture?: Record<string, unknown> }) =>
    request<EnvironmentRead>("/api/v1/environments", { method: "POST", body: JSON.stringify(body) }, token),
  deleteEnvironment: (token: string, environmentId: string) =>
    request<void>(`/api/v1/environments/${environmentId}`, { method: "DELETE" }, token),
  createCatalogConnection: (
    token: string,
    body: {
      environment_id: string;
      name: string;
      catalog_type: string;
      endpoint?: string;
      warehouse?: string;
      auth_ref?: string | null;
      settings?: Record<string, unknown>;
    }
  ) => request<CatalogConnectionRead>("/api/v1/connections/catalogs", { method: "POST", body: JSON.stringify(body) }, token),
  updateCatalogConnection: (
    token: string,
    connectionId: string,
    body: {
      environment_id?: string;
      name?: string;
      catalog_type?: string;
      endpoint?: string | null;
      warehouse?: string | null;
      auth_ref?: string | null;
      settings?: Record<string, unknown>;
      is_enabled?: boolean;
    }
  ) =>
    request<CatalogConnectionRead>(
      `/api/v1/connections/catalogs/${connectionId}`,
      { method: "PATCH", body: JSON.stringify(body) },
      token
    ),
  deleteCatalogConnection: (token: string, connectionId: string) =>
    request<void>(`/api/v1/connections/catalogs/${connectionId}`, { method: "DELETE" }, token),
  testCatalogConnection: (token: string, connectionId: string) =>
    request<ConnectionTestResult>(`/api/v1/connections/catalogs/${connectionId}/test`, { method: "POST", body: JSON.stringify({}) }, token),
  createObjectStoreConnection: (
    token: string,
    body: {
      environment_id: string;
      name: string;
      store_type: "s3" | "gcs" | "adls" | "hdfs" | "local";
      endpoint?: string;
      region?: string;
      auth_ref?: string | null;
      settings?: Record<string, unknown>;
    }
  ) =>
    request<ObjectStoreConnectionRead>("/api/v1/connections/object-stores", { method: "POST", body: JSON.stringify(body) }, token),
  updateObjectStoreConnection: (
    token: string,
    storeId: string,
    body: {
      environment_id?: string;
      name?: string;
      store_type?: "s3" | "gcs" | "adls" | "hdfs" | "local";
      endpoint?: string | null;
      region?: string | null;
      auth_ref?: string | null;
      settings?: Record<string, unknown>;
    }
  ) =>
    request<ObjectStoreConnectionRead>(
      `/api/v1/connections/object-stores/${storeId}`,
      { method: "PATCH", body: JSON.stringify(body) },
      token
    ),
  deleteObjectStoreConnection: (token: string, storeId: string) =>
    request<void>(`/api/v1/connections/object-stores/${storeId}`, { method: "DELETE" }, token),
  testObjectStoreConnection: (token: string, storeId: string) =>
    request<ConnectionTestResult>(`/api/v1/connections/object-stores/${storeId}/test`, { method: "POST", body: JSON.stringify({}) }, token),
  operations: (token: string) => request<OperationDescriptor[]>("/api/v1/operations/descriptors", {}, token),
  operationCategories: (token: string) =>
    request<OperationCategoryRead[]>("/api/v1/operations/descriptors/categories", {}, token),
  seedOperationDescriptors: (token: string) =>
    request<{ inserted: number; updated: number }>(
      "/api/v1/operations/descriptors/seed",
      { method: "POST", body: JSON.stringify({}) },
      token
    ),
  dryRun: (
    token: string,
    body: { operation_id: string; table_id?: string; params: Record<string, unknown> }
  ) =>
    request<OperationDryRunRead>("/api/v1/operations/dry-run", { method: "POST", body: JSON.stringify(body) }, token),
  execute: (token: string, body: { dry_run_id: string; confirmation?: string; idempotency_key?: string }) =>
    request<OperationExecuteRead>(
      "/api/v1/operations/execute",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  jobs: (token: string) => request<JobRead[]>("/api/v1/jobs", {}, token),
  jobRuns: (token: string, jobId: string) => request<JobRunRead[]>(`/api/v1/jobs/${jobId}/runs`, {}, token),
  jobLogs: (token: string, jobId: string) => request<JobLogRead[]>(`/api/v1/jobs/${jobId}/logs`, {}, token),
  cancelJob: (token: string, jobId: string) =>
    request<JobRead>(`/api/v1/jobs/${jobId}/cancel`, { method: "POST", body: JSON.stringify({}) }, token),
  audit: (token: string) => request<AuditEventRead[]>("/api/v1/audit", {}, token),
  approvals: (token: string) => request<ApprovalRead[]>("/api/v1/approvals", {}, token),
  decideApproval: (token: string, approvalId: string, body: { decision: "approved" | "rejected"; reason: string }) =>
    request<ApprovalRead>(
      `/api/v1/approvals/${approvalId}/decision`,
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  edition: (token: string) => request<EditionRead>("/api/v1/edition", {}, token),
  policies: (token: string) => request<AutomationPolicy[]>("/api/v1/policies", {}, token),
  createPolicy: (token: string, body: Record<string, unknown>) =>
    request<AutomationPolicy>("/api/v1/policies", { method: "POST", body: JSON.stringify(body) }, token),
  deletePolicy: (token: string, policyId: string) =>
    request<void>(`/api/v1/policies/${policyId}`, { method: "DELETE" }, token),
  clusteringAdvice: (token: string, tableId: string, body: Record<string, unknown>) =>
    request<ClusteringAdvice>(
      `/api/v1/tables/${tableId}/clustering-advice`,
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  parquetAdvice: (token: string, tableId: string) =>
    request<ParquetAdvice>(`/api/v1/tables/${tableId}/parquet-advice`, {}, token),
  distributionAdvice: (token: string, tableId: string) =>
    request<DistributionAdvice>(`/api/v1/tables/${tableId}/distribution-advice`, {}, token),
  cleanupPreview: (token: string, tableId: string, body: Record<string, unknown>) =>
    request<CleanupPreview>(
      `/api/v1/tables/${tableId}/cleanup/preview`,
      { method: "POST", body: JSON.stringify(body) },
      token
    )
};
