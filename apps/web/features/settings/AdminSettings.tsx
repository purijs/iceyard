"use client";

import { useState } from "react";

import type { ControlContext } from "@/app/page";
import { Badge, Button } from "@/components/ui";
import { Connections } from "@/features/connections/Connections";
import { Environments } from "@/features/environments/Environments";
import { api } from "@/lib/api";
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
        <RuntimeSettings
          token={token}
          environments={environments}
          connections={connections}
          computeBackends={computeBackends}
          onRefresh={onRefresh}
        />
      ) : null}
    </div>
  );
}

function RuntimeSettings({
  token,
  environments,
  connections,
  computeBackends,
  onRefresh
}: {
  token: string;
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
  computeBackends: ComputeBackendRead[];
  onRefresh: () => Promise<void>;
}) {
  const [environmentId, setEnvironmentId] = useState(environments[0]?.id ?? "");
  const [name, setName] = useState("spark-prod");
  const [backendType, setBackendType] = useState<ComputeBackendRead["backend_type"]>("spark");
  const [endpoint, setEndpoint] = useState("");
  const [principal, setPrincipal] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createBackend() {
    setError(null);
    setSubmitting(true);
    try {
      await api.createComputeBackend(token, {
        environment_id: environmentId,
        name: name.trim(),
        backend_type: backendType,
        settings: {
          endpoint: endpoint.trim() || undefined,
          principal: principal.trim() || undefined,
          execution_model: backendType === "duckdb" ? "local" : "external"
        }
      });
      await onRefresh();
      setEndpoint("");
      setPrincipal("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create compute backend.");
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteBackend(backend: ComputeBackendRead) {
    if (!window.confirm(`Delete compute backend "${backend.name}"?`)) return;
    setError(null);
    try {
      await api.deleteComputeBackend(token, backend.id);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete compute backend.");
    }
  }

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="border-b border-zinc-200 px-4 py-3">
          <div className="font-medium text-zinc-900">Add compute backend</div>
          <div className="mt-1 text-xs text-zinc-500">
            Required for heavy rewrites and query-backed execution. Metadata sync and catalog checks do not need compute.
          </div>
        </div>
        <div className="grid gap-3 p-4 lg:grid-cols-5">
          <label className="space-y-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Environment
            <select className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm normal-case tracking-normal text-zinc-900" value={environmentId} onChange={(event) => setEnvironmentId(event.target.value)}>
              {environments.map((environment) => (
                <option key={environment.id} value={environment.id}>{environment.name}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Runtime
            <select className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm normal-case tracking-normal text-zinc-900" value={backendType} onChange={(event) => setBackendType(event.target.value as ComputeBackendRead["backend_type"])}>
              {["spark", "trino", "flink", "duckdb", "embedded", "custom"].map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Name
            <input className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm normal-case tracking-normal text-zinc-900" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="space-y-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Endpoint
            <input className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm normal-case tracking-normal text-zinc-900" placeholder="spark://, trino://, http://..." value={endpoint} onChange={(event) => setEndpoint(event.target.value)} />
          </label>
          <label className="space-y-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
            Principal
            <input className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm normal-case tracking-normal text-zinc-900" placeholder="service account or role" value={principal} onChange={(event) => setPrincipal(event.target.value)} />
          </label>
          <div className="lg:col-span-5 flex items-center justify-between gap-3">
            <span className="text-xs text-zinc-400">Credentials should be configured by secret reference or runtime identity before enabling real execution adapters.</span>
            <Button variant="primary" onClick={createBackend} disabled={!environmentId || !name.trim() || submitting}>
              {submitting ? "Adding..." : "Add backend"}
            </Button>
          </div>
          {error ? <div className="lg:col-span-5 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
        </div>
      </section>

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
                {envBackends.map((backend) => (
                  <div key={backend.id} className="flex items-center justify-between gap-3 rounded-md border border-zinc-200 px-3 py-2">
                    <div>
                      <div className="font-medium text-zinc-900">{backend.name}</div>
                      <div className="font-mono text-xs text-zinc-500">{backend.backend_type} · {String(backend.settings.endpoint ?? "no endpoint")}</div>
                    </div>
                    <Button variant="danger" onClick={() => void deleteBackend(backend)}>Delete</Button>
                  </div>
                ))}
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
