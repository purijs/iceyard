"use client";

import { AlertTriangle } from "lucide-react";

import { Badge, formatBytes, Panel, toneForScore } from "@/components/ui";
import type { DashboardRead, TableRead } from "@/types/api";

export function Dashboard({ dashboard, tables }: { dashboard: DashboardRead | null; tables: TableRead[] }) {
  const stats = [
    ["Tables managed", dashboard?.table_count ?? tables.length, "indexed tables"],
    ["Fleet health", dashboard?.average_health ?? 0, "weighted score"],
    ["Needs attention", dashboard?.needs_attention ?? 0, "below 80"],
    ["Storage", formatBytes(dashboard?.storage_bytes ?? 0), "under management"],
    ["Active jobs", dashboard?.active_jobs ?? 0, "queued or running"]
  ];
  const risks = tables.filter((table) => table.health_score < 80).sort((a, b) => a.health_score - b.health_score).slice(0, 5);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {stats.map(([label, value, sub]) => (
          <Panel key={label as string}>
            <div className="text-xs text-zinc-500">{label}</div>
            <div className="mt-1 text-2xl font-semibold text-zinc-950">{value}</div>
            <div className="mt-0.5 text-xs text-zinc-400">{sub}</div>
          </Panel>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Health distribution">
          <div className="space-y-2 text-sm">
            {[
              ["Healthy", tables.filter((table) => table.health_score >= 80).length, "healthy"],
              ["Warning", tables.filter((table) => table.health_score >= 55 && table.health_score < 80).length, "warning"],
              ["Critical", tables.filter((table) => table.health_score < 55).length, "critical"]
            ].map(([label, count, tone]) => (
              <div key={label as string} className="flex items-center justify-between">
                <span className="text-zinc-600">{label}</span>
                <Badge tone={tone as "healthy" | "warning" | "critical"}>{count}</Badge>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Fleet health trend">
          <div className="flex h-32 items-center justify-center text-sm text-zinc-400">Trend data will load after scheduled health checks run.</div>
        </Panel>
        <Panel title="Alerts" right={<Badge tone="critical">1 blocking</Badge>}>
          <div className="space-y-3 text-sm text-zinc-600">
            <div className="flex gap-2">
              <AlertTriangle size={15} className="mt-0.5 text-red-600" />
              <span>Orphan cleanup remains blocked until path authority checks pass.</span>
            </div>
            <div className="flex gap-2">
              <AlertTriangle size={15} className="mt-0.5 text-amber-600" />
              <span>Format v3 promotions require reader compatibility review.</span>
            </div>
          </div>
        </Panel>
      </div>
      <Panel title="Top risks" right={<span className="text-xs text-zinc-400">ranked by health impact</span>} pad={false}>
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-medium">Table</th>
              <th className="px-4 py-2 font-medium">Primary issue</th>
              <th className="px-4 py-2 font-medium">Owner</th>
              <th className="px-4 py-2 font-medium">Health</th>
            </tr>
          </thead>
          <tbody>
            {risks.map((table) => (
              <tr key={table.id} className="border-b border-zinc-100 last:border-0">
                <td className="px-4 py-2.5 font-mono text-zinc-900">{table.name}</td>
                <td className="px-4 py-2.5 text-zinc-600">
                  {table.metrics && table.metrics.small_file_ratio > 0.4 ? `small-file ratio ${table.metrics.small_file_ratio}` : "metadata hygiene"}
                </td>
                <td className="px-4 py-2.5 text-zinc-600">{table.owner ?? <span className="text-amber-700">unassigned</span>}</td>
                <td className="px-4 py-2.5">
                  <Badge tone={toneForScore(table.health_score)}>{table.health_score}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
