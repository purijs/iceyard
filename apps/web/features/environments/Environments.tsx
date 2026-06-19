"use client";

import { GitBranch, HardDrive, Plus, ShieldCheck, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import type { CatalogConnectionRead, ComputeBackendRead, EnvironmentRead, ObjectStoreConnectionRead, TableRead } from "@/types/api";

export function Environments({
  token,
  environments,
  connections,
  objectStores,
  computeBackends,
  tables,
  onRefresh
}: {
  token: string;
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
  objectStores: ObjectStoreConnectionRead[];
  computeBackends: ComputeBackendRead[];
  tables: TableRead[];
  onRefresh: () => Promise<void>;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("");
  const [region, setRegion] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function createEnvironment() {
    setMessage(null);
    try {
      await api.createEnvironment(token, {
        name,
        kind: kind || name,
        region,
        posture: {
          approval_required: (kind || name) === "prod",
          protected_branches: ["main"]
        }
      });
      setShowAdd(false);
      await onRefresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to create environment.");
    }
  }

  async function deleteEnvironment(environment: EnvironmentRead, hasChildren: boolean) {
    if (hasChildren) {
      setMessage("Delete catalog, storage, and compute connections before deleting this environment.");
      return;
    }
    if (!window.confirm(`Delete environment "${environment.name}"?`)) return;
    setMessage(null);
    try {
      await api.deleteEnvironment(token, environment.id);
      await onRefresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to delete environment.");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-500">Environments are deployment scopes for catalog connections, approvals, and runtime routing.</p>
        <Button variant="primary" onClick={() => setShowAdd((current) => !current)}>
          <Plus size={14} /> Add environment
        </Button>
      </div>

      {showAdd ? (
        <Panel title="Add environment">
          <div className="grid gap-3 md:grid-cols-[1fr_180px_220px_auto]">
            <Field label="name" value={name} onChange={setName} placeholder="environment name" />
            <Field label="kind" value={kind} onChange={setKind} placeholder="defaults to name" />
            <Field label="region" value={region} onChange={setRegion} placeholder="region" />
            <div className="flex items-end">
              <Button variant="primary" disabled={!name || !kind} onClick={createEnvironment}>
                Save
              </Button>
            </div>
          </div>
        </Panel>
      ) : null}

      {message ? <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{message}</div> : null}

      <div className="grid gap-4 xl:grid-cols-2">
        {environments.map((environment) => {
          const envConnections = connections.filter((connection) => connection.environment_id === environment.id);
          const envStores = objectStores.filter((store) => store.environment_id === environment.id);
          const envBackends = computeBackends.filter((backend) => backend.environment_id === environment.id);
          const envTables = tables.filter((table) => table.environment_id === environment.id);
          const hasChildren = Boolean(envConnections.length || envStores.length || envBackends.length);
          return (
            <Panel
              key={environment.id}
              title={
                <span className="flex items-center gap-2">
                  {environment.name}
                  {environment.kind !== environment.name ? <Badge>{environment.kind}</Badge> : null}
                </span>
              }
              right={
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-400">{environment.region ?? "no region"}</span>
                  <Button
                    variant="danger"
                    disabled={hasChildren}
                    onClick={() => void deleteEnvironment(environment, hasChildren)}
                  >
                    <Trash2 size={14} /> Delete
                  </Button>
                </div>
              }
            >
              <div className="grid gap-3 md:grid-cols-5">
                <Metric label="Catalogs" value={envConnections.length} />
                <Metric label="Storage" value={envStores.length} />
                <Metric label="Tables" value={envTables.length} />
                <Metric label="Approval" value={environment.posture.approval_required ? "required" : "standard"} />
                <Metric label="Runtime" value={envBackends.some((backend) => backend.is_enabled) ? "configured" : "internal"} />
              </div>
              <div className="mt-4 space-y-2">
                {envConnections.map((connection) => (
                  <div key={connection.id} className="flex items-center justify-between rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm">
                    <span className="font-mono text-zinc-800">{connection.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-zinc-400">
                        {connection.catalog_type} · {connection.is_enabled ? "enabled" : "disabled"}
                      </span>
                    </div>
                  </div>
                ))}
                {!envConnections.length ? <div className="text-sm text-zinc-400">No catalog connections in this environment.</div> : null}
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                <Info icon={<ShieldCheck size={15} />} label="Safety posture" value={environment.posture.approval_required ? "Approvals enforced for state-changing production work." : "Standard gates apply."} />
                <Info icon={<GitBranch size={15} />} label="Refs" value={`Protected branches: ${protectedRefs(environment).join(", ") || "none"}`} />
                <Info icon={<HardDrive size={15} />} label="Compute" value={envBackends.length ? envBackends.map((backend) => backend.name).join(", ") : "No external backend configured."} />
              </div>
              {hasChildren ? (
                <p className="mt-3 text-xs text-zinc-400">
                  Delete is disabled until catalog connections, storage connections, and compute backends are removed from this environment. Indexed table cache is cleared on delete.
                </p>
              ) : null}
            </Panel>
          );
        })}
        {!environments.length ? <Panel><div className="text-sm text-zinc-400">No environments have been created.</div></Panel> : null}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-xs text-zinc-500">{label}</span>
      <input
        className="w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm outline-none placeholder:text-zinc-300 focus:border-zinc-500"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 truncate font-mono text-sm text-zinc-900">{value}</div>
    </div>
  );
}

function Info({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-md border border-zinc-200 p-3 text-sm">
      <div className="flex items-center gap-2 font-medium text-zinc-900">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-zinc-500">{value}</div>
    </div>
  );
}

function protectedRefs(environment: EnvironmentRead) {
  const refs = environment.posture.protected_branches;
  return Array.isArray(refs) ? refs.map(String) : [];
}
