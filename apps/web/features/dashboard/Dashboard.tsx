"use client";

import { AlertTriangle } from "lucide-react";

import { Badge, formatBytes, Panel } from "@/components/ui";
import type { JobRead, TableRead } from "@/types/api";
import type { ControlContext } from "@/app/page";

export function Dashboard({ tables, jobs, context }: { tables: TableRead[]; jobs: JobRead[]; context: ControlContext }) {
  const storageBytes = tables.reduce((sum, table) => sum + (table.metrics?.data_size_bytes ?? 0), 0);
  const issueRows = tables
    .map((table) => ({ table, issue: primaryIssue(table), severity: issueSeverity(table) }))
    .filter((row) => row.issue !== "No open issue");
  const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running").length;
  const stats = [
    ["Tables", tables.length, context.isAll ? "all scoped catalogs" : context.label],
    ["Storage", formatBytes(storageBytes), "indexed table data"],
    ["Open issues", issueRows.length, "maintenance signals"],
    ["Active jobs", activeJobs, "queued or running"],
    ["Scope", context.isAll ? "Summary" : "Catalog", context.label]
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {stats.map(([label, value, sub]) => (
          <Panel key={label as string}>
            <div className="text-xs text-zinc-500">{label}</div>
            <div className="mt-1 truncate text-2xl font-semibold text-zinc-950">{value}</div>
            <div className="mt-0.5 truncate text-xs text-zinc-400">{sub}</div>
          </Panel>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Issue mix">
          <div className="space-y-2 text-sm">
            {[
              ["Small files", tables.filter((table) => (table.metrics?.small_file_ratio ?? 0) >= 0.4).length, "warning"],
              ["Delete pressure", tables.filter((table) => (table.metrics?.delete_file_count ?? 0) > 100).length, "warning"],
              ["Snapshot pressure", tables.filter((table) => (table.metrics?.snapshot_count ?? 0) > 80).length, "critical"],
              ["Unassigned owner", tables.filter((table) => !table.owner).length, "critical"]
            ].map(([label, count, tone]) => (
              <div key={label as string} className="flex items-center justify-between">
                <span className="text-zinc-600">{label}</span>
                <Badge tone={tone as "warning" | "critical"}>{count}</Badge>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Runtime context">
          <div className="space-y-2 text-sm text-zinc-600">
            <div className="flex items-center justify-between gap-3">
              <span>Environment</span>
              <span className="font-mono text-zinc-900">{context.environment?.name ?? "all"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Catalog</span>
              <span className="font-mono text-zinc-900">{context.catalogConnection?.name ?? "all"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Mode</span>
              <span className="font-mono text-zinc-900">{context.isAll ? "summary" : "scoped"}</span>
            </div>
          </div>
        </Panel>
        <Panel title="Alerts" right={issueRows.length ? <Badge tone="warning">{issueRows.length} open</Badge> : null}>
          <div className="space-y-3 text-sm text-zinc-600">
            {issueRows.slice(0, 3).map(({ table, issue, severity }) => (
              <div key={`${table.id}-${issue}`} className="flex gap-2">
                <AlertTriangle size={15} className={`mt-0.5 ${severity === "critical" ? "text-red-600" : "text-amber-600"}`} />
                <span>
                  <span className="font-mono text-zinc-800">{table.name}</span> · {issue}
                </span>
              </div>
            ))}
            {!issueRows.length ? <div className="text-zinc-400">No open maintenance signals in this scope.</div> : null}
          </div>
        </Panel>
      </div>
      <Panel title="Recommended maintenance" right={<span className="text-xs text-zinc-400">ranked by issue severity</span>} pad={false}>
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-medium">Table</th>
              <th className="px-4 py-2 font-medium">Primary issue</th>
              <th className="px-4 py-2 font-medium">Recommended action</th>
              <th className="px-4 py-2 font-medium">Owner</th>
            </tr>
          </thead>
          <tbody>
            {issueRows.slice(0, 6).map(({ table, issue, severity }) => (
              <tr key={table.id} className="border-b border-zinc-100 last:border-0">
                <td className="px-4 py-2.5 font-mono text-zinc-900">{table.name}</td>
                <td className="px-4 py-2.5">
                  <Badge tone={severity === "critical" ? "critical" : "warning"}>{issue}</Badge>
                </td>
                <td className="px-4 py-2.5 text-zinc-600">{recommendedAction(table)}</td>
                <td className="px-4 py-2.5 text-zinc-600">{table.owner ?? <span className="text-amber-700">unassigned</span>}</td>
              </tr>
            ))}
            {!issueRows.length ? (
              <tr>
                <td className="px-4 py-8 text-center text-zinc-400" colSpan={4}>
                  No recommendations in this context.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

function primaryIssue(table: TableRead) {
  if (!table.owner) return "Owner missing";
  if ((table.metrics?.snapshot_count ?? 0) > 80) return "Snapshot pressure";
  if ((table.metrics?.small_file_ratio ?? 0) >= 0.4) return "Small files";
  if ((table.metrics?.delete_file_count ?? 0) > 100) return "Delete pressure";
  if (table.format_version >= 3) return "Format compatibility";
  return "No open issue";
}

function issueSeverity(table: TableRead) {
  if (!table.owner || (table.metrics?.snapshot_count ?? 0) > 100) return "critical";
  if (primaryIssue(table) !== "No open issue") return "warning";
  return "neutral";
}

function recommendedAction(table: TableRead) {
  if (!table.owner) return "Assign owner";
  if ((table.metrics?.snapshot_count ?? 0) > 80) return "Expire snapshots";
  if ((table.metrics?.small_file_ratio ?? 0) >= 0.4) return "Compact data files";
  if ((table.metrics?.delete_file_count ?? 0) > 100) return "Rewrite delete files";
  if (table.format_version >= 3) return "Review reader compatibility";
  return "Monitor";
}
