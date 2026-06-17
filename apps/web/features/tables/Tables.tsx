"use client";

import { useState } from "react";

import { Badge, Button, formatBytes, Panel, toneForScore } from "@/components/ui";
import type { HealthRead, TableRead } from "@/types/api";

export function Tables({
  tables,
  selected,
  health,
  onSelect,
  onOpenOperation
}: {
  tables: TableRead[];
  selected: TableRead | null;
  health: HealthRead | null;
  onSelect: (table: TableRead | null) => void;
  onOpenOperation: (operationId: string, table: TableRead) => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = tables.filter((table) => table.name.includes(query));
  if (selected) {
    return (
      <div className="space-y-4">
        <Button onClick={() => onSelect(null)} variant="ghost">
          Back to tables
        </Button>
        <Panel>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full border-8 border-zinc-100 text-lg font-semibold text-zinc-900">
              {selected.health_score}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-mono text-xl text-zinc-950">{selected.name}</h2>
                <Badge>v{selected.format_version}</Badge>
                <Badge tone={toneForScore(selected.health_score)}>{toneForScore(selected.health_score)}</Badge>
              </div>
              <div className="mt-1 font-mono text-sm text-zinc-400">{selected.location}</div>
            </div>
            <div className="ml-auto flex gap-2">
              <Button onClick={() => onOpenOperation("rewrite_data_files", selected)} variant="primary">
                Run maintenance
              </Button>
            </div>
          </div>
        </Panel>
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel title="Properties">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-zinc-500">Files</dt>
                <dd className="font-mono">{selected.metrics?.file_count.toLocaleString()}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Data size</dt>
                <dd className="font-mono">{formatBytes(selected.metrics?.data_size_bytes ?? 0)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Deletes</dt>
                <dd className="font-mono">{selected.metrics?.delete_file_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Snapshots</dt>
                <dd className="font-mono">{selected.metrics?.snapshot_count}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Owner</dt>
                <dd>{selected.owner ?? <span className="text-amber-700">unassigned</span>}</dd>
              </div>
            </dl>
          </Panel>
          <div className="lg:col-span-2">
            <Panel title="Health">
              <div className="space-y-3">
                {(health?.dimensions ?? []).map((dimension) => (
                  <div key={dimension.name}>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-zinc-600">
                        {dimension.name} <span className="text-zinc-400">{dimension.weight}%</span>
                      </span>
                      <span>{dimension.score}</span>
                    </div>
                    <div className="h-1.5 rounded bg-zinc-100">
                      <div className="h-1.5 rounded bg-zinc-900" style={{ width: `${dimension.score}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
        <Panel title="Recommended operations">
          <div className="flex flex-wrap gap-2">
            {(health?.recommended_actions ?? ["Compact data files"]).map((action) => (
              <Button key={action} onClick={() => onOpenOperation("rewrite_data_files", selected)}>
                {action}
              </Button>
            ))}
            <Button variant="danger" onClick={() => onOpenOperation("remove_orphan_files", selected)}>
              Remove orphan files
            </Button>
          </div>
        </Panel>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <input
        className="w-full max-w-sm rounded-md border border-zinc-300 px-3 py-2 text-sm"
        placeholder="Filter tables..."
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <Panel pad={false}>
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-medium">Table</th>
              <th className="px-4 py-2 font-medium">Fmt</th>
              <th className="px-4 py-2 font-medium">Health</th>
              <th className="px-4 py-2 font-medium">Files</th>
              <th className="px-4 py-2 font-medium">Small-file</th>
              <th className="px-4 py-2 font-medium">Size</th>
              <th className="px-4 py-2 font-medium">Owner</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((table) => (
              <tr key={table.id} onClick={() => onSelect(table)} className="cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-zinc-50">
                <td className="px-4 py-2.5 font-mono text-zinc-900">{table.name}</td>
                <td className="px-4 py-2.5">
                  <Badge>v{table.format_version}</Badge>
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={toneForScore(table.health_score)}>{table.health_score}</Badge>
                </td>
                <td className="px-4 py-2.5 font-mono">{table.metrics?.file_count.toLocaleString()}</td>
                <td className="px-4 py-2.5 font-mono">{table.metrics?.small_file_ratio}</td>
                <td className="px-4 py-2.5 font-mono">{formatBytes(table.metrics?.data_size_bytes ?? 0)}</td>
                <td className="px-4 py-2.5">{table.owner ?? <span className="text-amber-700">unassigned</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
