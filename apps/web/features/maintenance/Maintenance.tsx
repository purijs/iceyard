"use client";

import { Play, Wrench } from "lucide-react";

import { Badge, Button, formatBytes, Panel, toneForScore } from "@/components/ui";
import type { OperationDescriptor, TableRead } from "@/types/api";

const PLAN = [
  ["rewrite_data_files", "Compact data files"],
  ["rewrite_position_deletes", "Rewrite delete files"],
  ["rewrite_manifests", "Rewrite manifests"],
  ["expire_snapshots", "Expire snapshots"],
  ["remove_orphan_files", "Remove orphan files"]
] as const;

export function Maintenance({
  tables,
  operations,
  onOpenOperation
}: {
  tables: TableRead[];
  operations: OperationDescriptor[];
  onOpenOperation: (operationId: string, table: TableRead) => void;
}) {
  const operationIds = new Set(operations.map((operation) => operation.id));
  const recommendations = tables
    .filter((table) => table.health_score < 80)
    .sort((a, b) => a.health_score - b.health_score);

  return (
    <div className="space-y-4">
      <Panel title="Maintenance plan" right={<span className="text-xs text-zinc-400">{recommendations.length} tables with open recommendations</span>} pad={false}>
        <table className="w-full min-w-[900px] text-sm">
          <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-medium">Table</th>
              <th className="px-4 py-2 font-medium">Issue</th>
              <th className="px-4 py-2 font-medium">Size</th>
              <th className="px-4 py-2 font-medium">Health</th>
              <th className="px-4 py-2 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {recommendations.map((table) => (
              <tr key={table.id} className="border-b border-zinc-100 last:border-0">
                <td className="px-4 py-3 font-mono text-zinc-900">{table.name}</td>
                <td className="px-4 py-3 text-zinc-600">{primaryIssue(table)}</td>
                <td className="px-4 py-3 font-mono text-zinc-600">{formatBytes(table.metrics?.data_size_bytes ?? 0)}</td>
                <td className="px-4 py-3">
                  <Badge tone={toneForScore(table.health_score)}>{table.health_score}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Button onClick={() => onOpenOperation(bestOperation(table), table)}>
                    <span className="inline-flex items-center gap-2">
                      <Wrench size={15} />
                      Plan
                    </span>
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {PLAN.map(([operationId, label]) => (
          <Panel key={operationId}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-medium text-zinc-900">{label}</div>
                <div className="mt-1 text-sm text-zinc-500">{operationDescription(operationId)}</div>
              </div>
              {operationId === "expire_snapshots" || operationId === "remove_orphan_files" ? <Badge tone="warning">gated</Badge> : null}
            </div>
            <Button
              full
              disabled={!recommendations[0] || !operationIds.has(operationId)}
              onClick={() => recommendations[0] && onOpenOperation(operationId, recommendations[0])}
            >
              <span className="inline-flex items-center gap-2">
                <Play size={15} />
                Dry run
              </span>
            </Button>
          </Panel>
        ))}
      </div>
    </div>
  );
}

function primaryIssue(table: TableRead) {
  if ((table.metrics?.small_file_ratio ?? 0) >= 0.4) return `small-file ratio ${table.metrics?.small_file_ratio.toFixed(2)}`;
  if ((table.metrics?.delete_file_count ?? 0) > 100) return `${table.metrics?.delete_file_count.toLocaleString()} delete files`;
  if ((table.metrics?.snapshot_count ?? 0) > 80) return `${table.metrics?.snapshot_count.toLocaleString()} snapshots`;
  return "metadata hygiene";
}

function bestOperation(table: TableRead) {
  if ((table.metrics?.small_file_ratio ?? 0) >= 0.4) return "rewrite_data_files";
  if ((table.metrics?.delete_file_count ?? 0) > 100) return "rewrite_position_deletes";
  if ((table.metrics?.snapshot_count ?? 0) > 80) return "expire_snapshots";
  return "rewrite_manifests";
}

function operationDescription(operationId: string) {
  if (operationId === "rewrite_data_files") return "Bin-pack or sort compact small files.";
  if (operationId === "rewrite_position_deletes") return "Reduce position/equality delete pressure.";
  if (operationId === "rewrite_manifests") return "Consolidate manifest files for faster planning.";
  if (operationId === "expire_snapshots") return "Apply retention policy after protected-ref checks.";
  return "Delete unreferenced files after retention and path authority checks.";
}
