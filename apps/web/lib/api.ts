import type {
  AuditEventRead,
  BootstrapResponse,
  CatalogConnectionRead,
  DashboardRead,
  EnvironmentRead,
  HealthRead,
  JobRead,
  OperationCategoryRead,
  OperationDescriptor,
  OperationDryRunRead,
  OperationExecuteRead,
  RoleRead,
  TableRead,
  TokenResponse,
  UserDetailRead,
  UserRead
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("content-type", "application/json");
  if (token) {
    headers.set("authorization", `Bearer ${token}`);
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
  users: (token: string) => request<UserDetailRead[]>("/api/v1/users", {}, token),
  roles: (token: string) => request<RoleRead[]>("/api/v1/roles", {}, token),
  createUser: (token: string, body: { username: string; password: string; role_ids: string[] }) =>
    request<UserDetailRead>("/api/v1/users", { method: "POST", body: JSON.stringify(body) }, token),
  updateUser: (token: string, userId: string, body: { role_ids?: string[]; is_active?: boolean }) =>
    request<UserDetailRead>(`/api/v1/users/${userId}`, { method: "PATCH", body: JSON.stringify(body) }, token),
  dashboard: (token: string) => request<DashboardRead>("/api/v1/dashboard", {}, token),
  tables: (token: string) => request<TableRead[]>("/api/v1/tables", {}, token),
  tableHealth: (token: string, tableId: string) => request<HealthRead>(`/api/v1/tables/${tableId}/health`, {}, token),
  environments: (token: string) => request<EnvironmentRead[]>("/api/v1/environments", {}, token),
  connections: (token: string) => request<CatalogConnectionRead[]>("/api/v1/connections/catalogs", {}, token),
  createEnvironment: (token: string, body: { name: string; kind: string; region?: string }) =>
    request<EnvironmentRead>("/api/v1/environments", { method: "POST", body: JSON.stringify(body) }, token),
  createCatalogConnection: (
    token: string,
    body: {
      environment_id: string;
      name: string;
      catalog_type: string;
      endpoint?: string;
      warehouse?: string;
      settings?: Record<string, unknown>;
    }
  ) => request<CatalogConnectionRead>("/api/v1/connections/catalogs", { method: "POST", body: JSON.stringify(body) }, token),
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
    body: { operation_id: string; table_id?: string; engine?: string; params: Record<string, unknown> }
  ) =>
    request<OperationDryRunRead>("/api/v1/operations/dry-run", { method: "POST", body: JSON.stringify(body) }, token),
  execute: (token: string, body: { dry_run_id: string; confirmation?: string; idempotency_key?: string }) =>
    request<OperationExecuteRead>(
      "/api/v1/operations/execute",
      { method: "POST", body: JSON.stringify(body) },
      token
    ),
  jobs: (token: string) => request<JobRead[]>("/api/v1/jobs", {}, token),
  audit: (token: string) => request<AuditEventRead[]>("/api/v1/audit", {}, token)
};
