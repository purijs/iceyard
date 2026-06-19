"use client";

import {
  Boxes,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Search,
  Settings2,
  Shield,
  Sparkles,
  Table2,
  TerminalSquare,
  Wrench
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge, Button } from "@/components/ui";
import { Automation } from "@/features/automation/Automation";
import { Dashboard } from "@/features/dashboard/Dashboard";
import { Governance } from "@/features/governance/Governance";
import { Jobs } from "@/features/jobs/Jobs";
import { Maintenance } from "@/features/maintenance/Maintenance";
import { Operations } from "@/features/operations/Operations";
import { AdminSettings } from "@/features/settings/AdminSettings";
import { AuthGate } from "@/features/settings/AuthGate";
import { Tables } from "@/features/tables/Tables";
import { api } from "@/lib/api";
import type {
  ApprovalRead,
  AuditEventRead,
  CatalogConnectionRead,
  ComputeBackendRead,
  EnvironmentRead,
  HealthRead,
  JobRead,
  ObjectStoreConnectionRead,
  OperationDescriptor,
  RoleRead,
  TableRead,
  UserRead
} from "@/types/api";

const NAV = [
  ["overview", "Overview", LayoutDashboard],
  ["tables", "Tables", Table2],
  ["operations", "Operations", TerminalSquare],
  ["maintenance", "Maintenance", Wrench],
  ["jobs", "Jobs", ListChecks],
  ["governance", "Governance", Shield],
  ["automation", "Automation", Sparkles]
] as const;

type View = (typeof NAV)[number][0] | "admin";
type ContextId = string | "all";

export type ControlContext = {
  environmentId: ContextId;
  catalogConnectionId: ContextId;
  environment: EnvironmentRead | null;
  catalogConnection: CatalogConnectionRead | null;
  isAll: boolean;
  label: string;
};

const CONTEXT_STORAGE_KEY = "iceyard_context";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserRead | null>(null);
  const [view, setView] = useState<View>("overview");
  const [allTables, setAllTables] = useState<TableRead[]>([]);
  const [tables, setTables] = useState<TableRead[]>([]);
  const [selectedTable, setSelectedTable] = useState<TableRead | null>(null);
  const [selectedHealth, setSelectedHealth] = useState<HealthRead | null>(null);
  const [operations, setOperations] = useState<OperationDescriptor[]>([]);
  const [openOperationId, setOpenOperationId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobRead[]>([]);
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [audit, setAudit] = useState<AuditEventRead[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRead[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentRead[]>([]);
  const [connections, setConnections] = useState<CatalogConnectionRead[]>([]);
  const [objectStores, setObjectStores] = useState<ObjectStoreConnectionRead[]>([]);
  const [computeBackends, setComputeBackends] = useState<ComputeBackendRead[]>([]);
  const [environmentId, setEnvironmentId] = useState<ContextId>("all");
  const [catalogConnectionId, setCatalogConnectionId] = useState<ContextId>("all");
  const [error, setError] = useState<string | null>(null);
  const [accountMessage, setAccountMessage] = useState<string | null>(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const load = useCallback(async (activeToken: string) => {
    setError(null);
    try {
      const me = await api.me(activeToken);
      const [allTableRows, operationRows, jobRows, auditRows, approvalRows, envRows, connectionRows, objectStoreRows, backendRows, roleRows] =
        await Promise.all([
          api.tables(activeToken),
          api.operations(activeToken),
          api.jobs(activeToken),
          api.audit(activeToken),
          api.approvals(activeToken),
          api.environments(activeToken),
          api.connections(activeToken),
          api.objectStores(activeToken),
          api.computeBackends(activeToken),
          api.roles(activeToken)
        ]);
      setUser(me);
      setAllTables(allTableRows);
      setOperations(operationRows);
      setJobs(jobRows);
      setAudit(auditRows);
      setApprovals(approvalRows);
      setEnvironments(envRows);
      setConnections(connectionRows);
      setObjectStores(objectStoreRows);
      setComputeBackends(backendRows);
      setRoles(roleRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load workspace.");
    }
  }, []);

  const loadTables = useCallback(
    async (activeToken: string, activeEnvironmentId: ContextId, activeCatalogConnectionId: ContextId) => {
      setError(null);
      try {
        const tableRows = await api.tables(activeToken, {
          environmentId: activeEnvironmentId === "all" ? null : activeEnvironmentId,
          catalogConnectionId: activeCatalogConnectionId === "all" ? null : activeCatalogConnectionId
        });
        setTables(tableRows);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load tables.");
      }
    },
    []
  );

  useEffect(() => {
    const storedToken = localStorage.getItem("iceyard_token");
    const storedContext = localStorage.getItem(CONTEXT_STORAGE_KEY);
    if (storedContext) {
      try {
        const parsed = JSON.parse(storedContext) as {
          environmentId?: string;
          catalogConnectionId?: string;
        };
        setEnvironmentId(parsed.environmentId || "all");
        setCatalogConnectionId(parsed.catalogConnectionId || "all");
      } catch {
        localStorage.removeItem(CONTEXT_STORAGE_KEY);
      }
    }
    if (storedToken) {
      setToken(storedToken);
      void load(storedToken);
    }
  }, [load]);

  useEffect(() => {
    if (!token) return;
    void loadTables(token, environmentId, catalogConnectionId);
  }, [catalogConnectionId, environmentId, loadTables, token]);

  useEffect(() => {
    localStorage.setItem(CONTEXT_STORAGE_KEY, JSON.stringify({ environmentId, catalogConnectionId }));
  }, [catalogConnectionId, environmentId]);

  useEffect(() => {
    if (environmentId === "all") {
      if (catalogConnectionId !== "all") setCatalogConnectionId("all");
      return;
    }
    const envExists = environments.some((environment) => environment.id === environmentId);
    if (!envExists && environments.length) {
      setEnvironmentId("all");
      setCatalogConnectionId("all");
      return;
    }
    const envConnections = connections.filter((connection) => connection.environment_id === environmentId);
    if (!envConnections.length) {
      if (catalogConnectionId !== "all") setCatalogConnectionId("all");
      return;
    }
    if (catalogConnectionId === "all" || !envConnections.some((connection) => connection.id === catalogConnectionId)) {
      setCatalogConnectionId(envConnections[0].id);
    }
  }, [catalogConnectionId, connections, environmentId, environments]);

  useEffect(() => {
    if (selectedTable && !tables.some((table) => table.id === selectedTable.id)) {
      setSelectedTable(null);
      setSelectedHealth(null);
    }
  }, [selectedTable, tables]);

  useEffect(() => {
    if (token && selectedTable) {
      void api.tableHealth(token, selectedTable.id).then(setSelectedHealth).catch(() => setSelectedHealth(null));
    }
  }, [token, selectedTable]);

  const selectedEnvironment = environments.find((environment) => environment.id === environmentId) ?? null;
  const selectedConnection = connections.find((connection) => connection.id === catalogConnectionId) ?? null;
  const context: ControlContext = useMemo(
    () => ({
      environmentId,
      catalogConnectionId,
      environment: selectedEnvironment,
      catalogConnection: selectedConnection,
      isAll: environmentId === "all" || catalogConnectionId === "all" || !selectedConnection,
      label:
        environmentId === "all"
          ? "All environments"
          : selectedConnection && selectedEnvironment
            ? `${selectedEnvironment.name} / ${selectedConnection.name}`
            : selectedEnvironment?.name ?? "No catalog selected"
    }),
    [catalogConnectionId, environmentId, selectedConnection, selectedEnvironment]
  );

  const visibleJobs = useMemo(
    () =>
      jobs.filter((job) => {
        if (context.environmentId !== "all" && job.environment_id && job.environment_id !== context.environmentId) return false;
        if (context.catalogConnectionId !== "all" && job.catalog_connection_id && job.catalog_connection_id !== context.catalogConnectionId) return false;
        return true;
      }),
    [context.catalogConnectionId, context.environmentId, jobs]
  );
  const searchResults = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return [];
    const tableResults = tables
      .filter((table) => `${table.name} ${table.location} ${table.owner ?? ""}`.toLowerCase().includes(query))
      .slice(0, 5)
      .map((table) => ({
        id: `table-${table.id}`,
        kind: "Table",
        title: table.name,
        subtitle: table.location,
        action: () => {
          setSelectedTable(table);
          setView("tables");
        }
      }));
    const jobResults = visibleJobs
      .filter((job) =>
        `${job.id} ${job.kind} ${job.operation_id ?? ""} ${job.status} ${job.table_name ?? ""}`
          .toLowerCase()
          .includes(query)
      )
      .slice(0, 4)
      .map((job) => ({
        id: `job-${job.id}`,
        kind: "Job",
        title: job.id,
        subtitle: `${job.operation_id ?? job.kind} · ${job.table_name ?? "catalog scope"}`,
        action: () => {
          setSelectedTable(null);
          setView("jobs");
        }
      }));
    const operationResults = operations
      .filter((operation) => `${operation.name} ${operation.id} ${operation.category}`.toLowerCase().includes(query))
      .slice(0, 4)
      .map((operation) => ({
        id: `operation-${operation.id}`,
        kind: "Operation",
        title: operation.name,
        subtitle: operation.id,
        action: () => {
          setSelectedTable(null);
          setOpenOperationId(operation.id);
          setView("operations");
        }
      }));
    return [...tableResults, ...jobResults, ...operationResults].slice(0, 10);
  }, [operations, searchQuery, tables, visibleJobs]);

  if (!token) {
    return (
      <AuthGate
        onToken={(nextToken) => {
          setToken(nextToken);
          void load(nextToken);
          void loadTables(nextToken, environmentId, catalogConnectionId);
        }}
      />
    );
  }

  const title =
    view === "tables" && selectedTable
      ? "Table detail"
      : view === "admin"
        ? "Admin Settings"
        : NAV.find(([key]) => key === view)?.[1] ?? "Overview";

  const openOperation = (operationId: string, table?: TableRead | null) => {
    setSelectedTable(table ?? null);
    setOpenOperationId(operationId);
    setView("operations");
  };

  const handleRefresh = async () => {
    if (!token) return;
    await load(token);
    await loadTables(token, environmentId, catalogConnectionId);
  };

  const handleLogout = async () => {
    try {
      if (token) await api.logout(token);
    } catch {
      // Clear the local session even if the server-side token has already expired.
    }
    localStorage.removeItem("iceyard_token");
    setToken(null);
    setUser(null);
    setSelectedTable(null);
    setView("overview");
  };

  const runSearchResult = (result: (typeof searchResults)[number]) => {
    result.action();
    setSearchQuery("");
    setSearchOpen(false);
  };

  const handlePasswordChange = async () => {
    if (!token) return;
    setAccountMessage(null);
    try {
      await api.changePassword(token, { current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setAccountMessage("Password updated.");
    } catch (err) {
      setAccountMessage(err instanceof Error ? err.message : "Unable to update password.");
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-50 text-zinc-950">
      <aside className="flex w-64 shrink-0 flex-col border-r border-zinc-200 bg-white">
        <div className="flex items-center gap-3 border-b border-zinc-200 px-4 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-zinc-950 text-white">
            <Boxes size={17} />
          </div>
          <div>
            <div className="text-sm font-semibold">Iceyard</div>
            <div className="text-xs text-zinc-400">Iceberg control plane</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {NAV.map(([key, label, Icon]) => (
            <button
              key={key}
              onClick={() => {
                setView(key);
                if (key !== "tables") setSelectedTable(null);
              }}
              className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm transition ${view === key ? "bg-zinc-100 font-medium text-zinc-950" : "text-zinc-600 hover:bg-zinc-50"}`}
            >
              <Icon size={16} className={view === key ? "text-zinc-950" : "text-zinc-400"} />
              {label}
            </button>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center gap-3 border-b border-zinc-200 bg-white px-5 py-3">
          <h1 className="text-base font-medium">{title}</h1>
          <div className="ml-auto flex min-w-0 items-center gap-3">
            <div className="relative hidden xl:block">
              <label className="flex w-72 items-center gap-2 rounded-md border border-zinc-300 px-3 py-1.5 focus-within:border-zinc-500">
                <Search size={14} className="text-zinc-400" />
                <input
                  className="w-full bg-transparent text-sm outline-none placeholder:text-zinc-400"
                  placeholder="Search tables, jobs..."
                  value={searchQuery}
                  onFocus={() => setSearchOpen(true)}
                  onBlur={() => window.setTimeout(() => setSearchOpen(false), 120)}
                  onChange={(event) => {
                    setSearchQuery(event.target.value);
                    setSearchOpen(true);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && searchResults[0]) runSearchResult(searchResults[0]);
                    if (event.key === "Escape") setSearchOpen(false);
                  }}
                />
              </label>
              {searchOpen && searchQuery.trim() ? (
                <div className="absolute right-0 top-10 z-50 w-[420px] overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-xl">
                  {searchResults.length ? (
                    <div className="max-h-96 overflow-auto py-1">
                      {searchResults.map((result) => (
                        <button
                          key={result.id}
                          className="flex w-full items-start gap-3 px-3 py-2 text-left hover:bg-zinc-50"
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => runSearchResult(result)}
                        >
                          <Badge>{result.kind}</Badge>
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-medium text-zinc-900">{result.title}</span>
                            <span className="block truncate text-xs text-zinc-400">{result.subtitle}</span>
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="px-3 py-4 text-sm text-zinc-400">No matching tables, jobs, or operations.</div>
                  )}
                </div>
              ) : null}
            </div>
            <ContextSelector
              environments={environments}
              connections={connections}
              environmentId={environmentId}
              catalogConnectionId={catalogConnectionId}
              onEnvironmentChange={(nextEnvironmentId) => {
                setEnvironmentId(nextEnvironmentId);
                if (nextEnvironmentId === "all") {
                  setCatalogConnectionId("all");
                  return;
                }
                const nextConnection = connections.find((connection) => connection.environment_id === nextEnvironmentId);
                setCatalogConnectionId(nextConnection?.id ?? "all");
              }}
              onConnectionChange={setCatalogConnectionId}
            />
            <ContextBadge context={context} />
            <div className="relative">
              <button
                className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-950 text-sm font-medium text-white"
                onClick={() => setAccountMenuOpen((current) => !current)}
                title="Account"
              >
                {(user?.username?.[0] ?? "A").toUpperCase()}
              </button>
              {accountMenuOpen ? (
                <div className="absolute right-0 top-10 z-50 w-80 rounded-lg border border-zinc-200 bg-white p-3 shadow-xl">
                  <div className="mb-3 border-b border-zinc-100 pb-3">
                    <div className="text-sm font-medium text-zinc-900">{user?.username ?? "admin"}</div>
                    <div className="text-xs text-zinc-400">signed in</div>
                  </div>
                  <div className="space-y-1">
                    <button
                      className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-zinc-700 hover:bg-zinc-50"
                      onClick={() => {
                        setView("admin");
                        setSelectedTable(null);
                        setAccountMenuOpen(false);
                      }}
                    >
                      <Settings2 size={15} />
                      Admin Settings
                    </button>
                    <details className="rounded-md px-2 py-2 text-sm text-zinc-700">
                      <summary className="flex cursor-pointer list-none items-center gap-2">
                        <KeyRound size={15} />
                        Change password
                      </summary>
                      <div className="mt-3 space-y-2">
                        <input
                          className="w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm"
                          type="password"
                          placeholder="Current password"
                          value={currentPassword}
                          onChange={(event) => setCurrentPassword(event.target.value)}
                        />
                        <input
                          className="w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm"
                          type="password"
                          placeholder="New password"
                          value={newPassword}
                          onChange={(event) => setNewPassword(event.target.value)}
                        />
                        <Button full disabled={!currentPassword || !newPassword} onClick={handlePasswordChange}>
                          Update password
                        </Button>
                        {accountMessage ? <div className="text-xs text-zinc-500">{accountMessage}</div> : null}
                      </div>
                    </details>
                    <button
                      className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-zinc-700 hover:bg-zinc-50"
                      onClick={handleLogout}
                    >
                      <LogOut size={15} />
                      Sign out
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-5">
          {error ? <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
          {view === "overview" ? <Dashboard tables={tables} jobs={visibleJobs} context={context} /> : null}
          {view === "tables" ? (
            <Tables
              token={token}
              tables={tables}
              environments={environments}
              connections={connections}
              context={context}
              selected={selectedTable}
              health={selectedHealth}
              operations={operations}
              onSelect={setSelectedTable}
              onOpenOperation={openOperation}
            />
          ) : null}
          {view === "operations" ? (
            <Operations
              token={token}
              operations={operations}
              tables={tables}
              selectedTable={selectedTable}
              context={context}
              openOperationId={openOperationId}
              onClose={() => setOpenOperationId(null)}
              onExecuted={handleRefresh}
            />
          ) : null}
          {view === "maintenance" ? (
            <Maintenance tables={tables} operations={operations} context={context} onOpenOperation={openOperation} />
          ) : null}
          {view === "jobs" ? <Jobs token={token} jobs={visibleJobs} context={context} onRefresh={handleRefresh} /> : null}
          {view === "governance" ? (
            <Governance
              token={token}
              roles={roles}
              audit={audit}
              approvals={approvals}
              operations={operations}
              context={context}
              onRefresh={handleRefresh}
            />
          ) : null}
          {view === "automation" ? (
            <Automation token={token} tables={tables} operations={operations} context={context} onOpenOperation={openOperation} />
          ) : null}
          {view === "admin" ? (
            <AdminSettings
              token={token}
              environments={environments}
              connections={connections}
              objectStores={objectStores}
              computeBackends={computeBackends}
              tables={allTables}
              context={context}
              onRefresh={handleRefresh}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}

function ContextSelector({
  environments,
  connections,
  environmentId,
  catalogConnectionId,
  onEnvironmentChange,
  onConnectionChange
}: {
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
  environmentId: ContextId;
  catalogConnectionId: ContextId;
  onEnvironmentChange: (environmentId: ContextId) => void;
  onConnectionChange: (connectionId: ContextId) => void;
}) {
  const envConnections =
    environmentId === "all" ? [] : connections.filter((connection) => connection.environment_id === environmentId);
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-md border border-zinc-300 bg-white p-1 text-sm">
      <span className="pl-2 text-xs text-zinc-400">context</span>
      <select
        className="max-w-36 rounded bg-transparent px-1 py-1 text-zinc-700 outline-none"
        value={environmentId}
        onChange={(event) => onEnvironmentChange(event.target.value)}
      >
        <option value="all">All environments</option>
        {environments.map((environment) => (
          <option key={environment.id} value={environment.id}>
            {environment.name}
          </option>
        ))}
      </select>
      <select
        className="max-w-44 rounded bg-transparent px-1 py-1 text-zinc-700 outline-none disabled:text-zinc-400"
        value={catalogConnectionId}
        disabled={environmentId === "all" || !envConnections.length}
        onChange={(event) => onConnectionChange(event.target.value)}
      >
        {environmentId === "all" ? <option value="all">All catalogs</option> : null}
        {environmentId !== "all" && !envConnections.length ? <option value="all">No catalog</option> : null}
        {envConnections.map((connection) => (
          <option key={connection.id} value={connection.id}>
            {connection.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function ContextBadge({ context }: { context: ControlContext }) {
  if (context.isAll) {
    return <Badge tone="neutral">all environments</Badge>;
  }
  return (
    <Badge tone={context.catalogConnection?.is_enabled ? "healthy" : "neutral"}>
      {context.catalogConnection?.catalog_type ?? "catalog"} · {context.catalogConnection?.is_enabled ? "connected" : "disabled"}
    </Badge>
  );
}
