"use client";

import { useState } from "react";

import type { ControlContext } from "@/app/page";
import { Badge } from "@/components/ui";
import { Connections } from "@/features/connections/Connections";
import { Environments } from "@/features/environments/Environments";
import type { CatalogConnectionRead, ComputeBackendRead, EnvironmentRead, ObjectStoreConnectionRead, TableRead } from "@/types/api";

type SettingsTab = "connections" | "environments" | "runtime";

export function AdminSettings({
  token,
  environments,
  connections,
  objectStores,
  computeBackends,
  tables,
  context,
  onRefresh
}: {
  token: string;
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
  objectStores: ObjectStoreConnectionRead[];
  computeBackends: ComputeBackendRead[];
  tables: TableRead[];
  context: ControlContext;
  onRefresh: () => Promise<void>;
}) {
  const [tab, setTab] = useState<SettingsTab>("connections");

  return (
    <div className="space-y-4">
      <div className="border-b border-zinc-200">
        <div className="flex flex-wrap items-center gap-5">
          {[
            ["connections", "Connections"],
            ["environments", "Environments"],
            ["runtime", "Runtime"]
          ].map(([key, label]) => (
            <button
              key={key}
              className={`border-b-2 px-1 py-3 text-sm ${
                tab === key
                  ? "border-zinc-950 font-medium text-zinc-950"
                  : "border-transparent text-zinc-500 hover:text-zinc-900"
              }`}
              onClick={() => setTab(key as SettingsTab)}
            >
              {label}
            </button>
          ))}
          <div className="ml-auto text-xs text-zinc-400">
            Setup scope for catalog access, inventory, and execution routing.
          </div>
        </div>
      </div>

      {tab === "connections" ? (
        <Connections
          token={token}
          environments={environments}
          connections={connections}
          objectStores={objectStores}
          computeBackends={computeBackends}
          tables={tables}
          context={context}
          onRefresh={onRefresh}
        />
      ) : null}
      {tab === "environments" ? (
        <Environments
          token={token}
          environments={environments}
          connections={connections}
          objectStores={objectStores}
          computeBackends={computeBackends}
          tables={tables}
          onRefresh={onRefresh}
        />
      ) : null}
      {tab === "runtime" ? (
        <RuntimeSettings environments={environments} connections={connections} computeBackends={computeBackends} />
      ) : null}
    </div>
  );
}

function RuntimeSettings({
  environments,
  connections,
  computeBackends
}: {
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
  computeBackends: ComputeBackendRead[];
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {environments.map((environment) => {
        const envConnections = connections.filter((connection) => connection.environment_id === environment.id);
        const envBackends = computeBackends.filter((backend) => backend.environment_id === environment.id && backend.is_enabled);
        const writableCatalog = envConnections.some((connection) => connection.is_enabled);
        return (
          <section key={environment.id} className="rounded-lg border border-zinc-200 bg-white shadow-sm">
            <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
              <div className="font-medium text-zinc-900">{environment.name}</div>
              {environment.kind !== environment.name ? <Badge>{environment.kind}</Badge> : null}
            </div>
            <div className="space-y-3 p-4 text-sm">
              <RuntimeRow
                label="Native catalog operations"
                value={writableCatalog ? "enabled" : "unavailable"}
                tone={writableCatalog ? "healthy" : "neutral"}
                detail="Metadata, refs, schema, and catalog-scoped dry-runs use the selected catalog connection."
              />
              <RuntimeRow
                label="Internal worker"
                value="enabled"
                tone="healthy"
                detail="Runs safety gates, compiled-command snapshots, approvals, audit, and logs."
              />
              <RuntimeRow
                label="Compute backend"
                value={envBackends.length ? envBackends.map((backend) => backend.name).join(", ") : "not configured"}
                tone={envBackends.length ? "healthy" : "warning"}
                detail="Required before heavy rewrites, query-backed preview, and large table maintenance can execute."
              />
            </div>
          </section>
        );
      })}
      {!environments.length ? (
        <section className="rounded-lg border border-zinc-200 bg-white p-4 text-sm text-zinc-400">
          No environments have been created.
        </section>
      ) : null}
    </div>
  );
}

function RuntimeRow({
  label,
  value,
  detail,
  tone
}: {
  label: string;
  value: string;
  detail: string;
  tone: "healthy" | "warning" | "neutral";
}) {
  return (
    <div className="rounded-md border border-zinc-200 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="font-medium text-zinc-900">{label}</div>
        <Badge tone={tone}>{value}</Badge>
      </div>
      <div className="mt-1 text-xs text-zinc-500">{detail}</div>
    </div>
  );
}
