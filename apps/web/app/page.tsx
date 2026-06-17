"use client";

import { Boxes, Database, GitBranch, LayoutDashboard, ListChecks, Search, Shield, Sparkles, Table2, TerminalSquare, Users2, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui";
import { Dashboard } from "@/features/dashboard/Dashboard";
import { Automation } from "@/features/automation/Automation";
import { Connections } from "@/features/connections/Connections";
import { Environments } from "@/features/environments/Environments";
import { Governance } from "@/features/governance/Governance";
import { Jobs } from "@/features/jobs/Jobs";
import { Maintenance } from "@/features/maintenance/Maintenance";
import { Operations } from "@/features/operations/Operations";
import { AuthGate } from "@/features/settings/AuthGate";
import { Tables } from "@/features/tables/Tables";
import { Users } from "@/features/users/Users";
import { api } from "@/lib/api";
import type {
  AuditEventRead,
  CatalogConnectionRead,
  DashboardRead,
  EnvironmentRead,
  HealthRead,
  JobRead,
  OperationDescriptor,
  RoleRead,
  TableRead,
  UserDetailRead,
  UserRead
} from "@/types/api";

const NAV = [
  ["overview", "Overview", LayoutDashboard],
  ["connections", "Connections", Database],
  ["tables", "Tables", Table2],
  ["operations", "Operations", TerminalSquare],
  ["maintenance", "Maintenance", Wrench],
  ["jobs", "Jobs", ListChecks],
  ["environments", "Environments", GitBranch],
  ["governance", "Governance", Shield],
  ["automation", "Automation", Sparkles],
  ["users", "Users", Users2]
] as const;

type View = (typeof NAV)[number][0];

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserRead | null>(null);
  const [view, setView] = useState<View>("overview");
  const [dashboard, setDashboard] = useState<DashboardRead | null>(null);
  const [tables, setTables] = useState<TableRead[]>([]);
  const [selectedTable, setSelectedTable] = useState<TableRead | null>(null);
  const [selectedHealth, setSelectedHealth] = useState<HealthRead | null>(null);
  const [operations, setOperations] = useState<OperationDescriptor[]>([]);
  const [openOperationId, setOpenOperationId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobRead[]>([]);
  const [users, setUsers] = useState<UserDetailRead[]>([]);
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [audit, setAudit] = useState<AuditEventRead[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentRead[]>([]);
  const [connections, setConnections] = useState<CatalogConnectionRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (activeToken: string) => {
      setError(null);
      try {
        const me = await api.me(activeToken);
        const tableRows = await api.tables(activeToken);
        const [dash, operationRows, jobRows, auditRows, envRows, connectionRows, userRows, roleRows] = await Promise.all([
          api.dashboard(activeToken),
          api.operations(activeToken),
          api.jobs(activeToken),
          api.audit(activeToken),
          api.environments(activeToken),
          api.connections(activeToken),
          api.users(activeToken),
          api.roles(activeToken)
        ]);
        setUser(me);
        setDashboard(dash);
        setTables(tableRows);
        setOperations(operationRows);
        setJobs(jobRows);
        setUsers(userRows);
        setRoles(roleRows);
        setAudit(auditRows);
        setEnvironments(envRows);
        setConnections(connectionRows);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load workspace.");
      }
    },
    []
  );

  useEffect(() => {
    const stored = localStorage.getItem("iceyard_token");
    if (stored) {
      setToken(stored);
      void load(stored);
    }
  }, [load]);

  useEffect(() => {
    if (token && selectedTable) {
      void api.tableHealth(token, selectedTable.id).then(setSelectedHealth).catch(() => setSelectedHealth(null));
    }
  }, [token, selectedTable]);

  if (!token) {
    return (
      <AuthGate
        onToken={(nextToken) => {
          setToken(nextToken);
          void load(nextToken);
        }}
      />
    );
  }

  const title = view === "tables" && selectedTable ? "Table detail" : NAV.find(([key]) => key === view)?.[1] ?? "Overview";
  const openOperation = (operationId: string, table: TableRead) => {
    setSelectedTable(table);
    setOpenOperationId(operationId);
    setView("operations");
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
        <div className="border-t border-zinc-200 p-3">
          <div className="rounded-md bg-zinc-50 px-3 py-2 text-xs">
            <div className="font-medium text-zinc-800">{user?.username ?? "User"}</div>
            <div className="text-zinc-400">signed in</div>
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center gap-3 border-b border-zinc-200 bg-white px-5 py-3">
          <h1 className="text-base font-medium">{title}</h1>
          <div className="ml-auto flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-md border border-zinc-300 px-3 py-1.5 md:flex">
              <Search size={14} className="text-zinc-400" />
              <span className="text-sm text-zinc-400">Search tables, jobs...</span>
            </div>
            <Badge>{connections.length} connections</Badge>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-5">
          {error ? <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
          {view === "overview" ? <Dashboard dashboard={dashboard} tables={tables} /> : null}
          {view === "connections" ? (
            <Connections token={token} environments={environments} connections={connections} onRefresh={() => load(token)} />
          ) : null}
          {view === "tables" ? (
            <Tables
              token={token}
              tables={tables}
              environments={environments}
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
              selectedTable={selectedTable}
              openOperationId={openOperationId}
              onClose={() => setOpenOperationId(null)}
              onExecuted={() => load(token)}
            />
          ) : null}
          {view === "maintenance" ? <Maintenance tables={tables} operations={operations} onOpenOperation={openOperation} /> : null}
          {view === "jobs" ? (
            <Jobs token={token} jobs={jobs} tables={tables} operations={operations} onOpenOperation={openOperation} onRefresh={() => load(token)} />
          ) : null}
          {view === "environments" ? <Environments environments={environments} connections={connections} /> : null}
          {view === "users" ? (
            <Users token={token} users={users} roles={roles} currentUserId={user?.id ?? null} onRefresh={() => load(token)} />
          ) : null}
          {view === "governance" ? <Governance audit={audit} /> : null}
          {view === "automation" ? <Automation token={token} tables={tables} operations={operations} onOpenOperation={openOperation} /> : null}
        </main>
      </div>
    </div>
  );
}
