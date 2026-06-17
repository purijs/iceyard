"use client";

import { GitBranch, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { Badge, Panel } from "@/components/ui";
import type { CatalogConnectionRead, EnvironmentRead } from "@/types/api";

export function Environments({
  environments,
  connections
}: {
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {environments.map((environment) => {
        const envConnections = connections.filter((connection) => connection.environment_id === environment.id);
        return (
          <Panel
            key={environment.id}
            title={
              <span className="flex items-center gap-2">
                {environment.name}
                <Badge>{environment.kind}</Badge>
              </span>
            }
            right={<span className="text-xs text-zinc-400">{environment.region ?? "no region"}</span>}
          >
            <div className="grid gap-3 md:grid-cols-3">
              <Metric label="Catalogs" value={envConnections.length} />
              <Metric label="Approval" value={environment.posture.approval_required ? "required" : "standard"} />
              <Metric label="Protected refs" value={protectedRefs(environment).join(", ") || "none"} />
            </div>
            <div className="mt-4 space-y-2">
              {envConnections.map((connection) => (
                <div key={connection.id} className="flex items-center justify-between rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm">
                  <span className="font-mono text-zinc-800">{connection.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge>{connection.catalog_type}</Badge>
                    <Badge tone={connection.is_enabled ? "healthy" : "neutral"}>{connection.is_enabled ? "enabled" : "disabled"}</Badge>
                  </div>
                </div>
              ))}
              {!envConnections.length ? <div className="text-sm text-zinc-400">No connections in this environment.</div> : null}
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              <Info icon={<ShieldCheck size={15} />} label="Safety posture" value={environment.posture.approval_required ? "Approvals enforced for state-changing production work." : "Standard gates apply."} />
              <Info icon={<GitBranch size={15} />} label="Refs" value={`Protected branches: ${protectedRefs(environment).join(", ") || "none"}`} />
            </div>
          </Panel>
        );
      })}
      {!environments.length ? <Panel><div className="text-sm text-zinc-400">No environments have been created.</div></Panel> : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 font-mono text-sm text-zinc-900">{value}</div>
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
