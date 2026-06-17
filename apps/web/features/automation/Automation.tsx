"use client";

import { CalendarClock, Play, Sparkles } from "lucide-react";

import { Badge, Button, Panel } from "@/components/ui";
import type { OperationDescriptor, TableRead } from "@/types/api";

const POLICIES = [
  {
    name: "Weekly compaction",
    match: "prod.analytics.*",
    operation: "rewrite_data_files",
    schedule: "Sun 02:00",
    status: "enabled"
  },
  {
    name: "Snapshot retention",
    match: "dev.*",
    operation: "expire_snapshots",
    schedule: "daily 01:00",
    status: "approval gated"
  },
  {
    name: "Manifest hygiene",
    match: "*",
    operation: "rewrite_manifests",
    schedule: "after 50 manifests",
    status: "enabled"
  }
];

export function Automation({
  tables,
  operations,
  onOpenOperation
}: {
  tables: TableRead[];
  operations: OperationDescriptor[];
  onOpenOperation: (operationId: string, table: TableRead) => void;
}) {
  const operationById = new Map(operations.map((operation) => [operation.id, operation]));
  const target = tables.find((table) => table.health_score < 80) ?? tables[0];

  return (
    <div className="space-y-4">
      <Panel title="Policy bindings" right={<span className="text-xs text-zinc-400">{POLICIES.length} active policies</span>} pad={false}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px] text-sm">
            <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-medium">Policy</th>
                <th className="px-4 py-2 font-medium">Match</th>
                <th className="px-4 py-2 font-medium">Operation</th>
                <th className="px-4 py-2 font-medium">Schedule</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {POLICIES.map((policy) => (
                <tr key={policy.name} className="border-b border-zinc-100 last:border-0">
                  <td className="px-4 py-3 font-medium text-zinc-900">{policy.name}</td>
                  <td className="px-4 py-3 font-mono text-zinc-600">{policy.match}</td>
                  <td className="px-4 py-3">
                    <Badge>{operationById.get(policy.operation)?.name ?? policy.operation}</Badge>
                  </td>
                  <td className="px-4 py-3 text-zinc-600">{policy.schedule}</td>
                  <td className="px-4 py-3">
                    <Badge tone={policy.status === "enabled" ? "healthy" : "warning"}>{policy.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button disabled={!target} onClick={() => target && onOpenOperation(policy.operation, target)}>
                      Dry run now
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-4 md:grid-cols-3">
        <Panel>
          <div className="flex items-start gap-3">
            <Sparkles size={18} className="text-zinc-500" />
            <div>
              <div className="font-medium text-zinc-900">Recommendation triggers</div>
              <p className="mt-1 text-sm text-zinc-500">Bind health findings to operation descriptors and prefilled dry-run parameters.</p>
            </div>
          </div>
        </Panel>
        <Panel>
          <div className="flex items-start gap-3">
            <CalendarClock size={18} className="text-zinc-500" />
            <div>
              <div className="font-medium text-zinc-900">Schedules</div>
              <p className="mt-1 text-sm text-zinc-500">Cron and threshold policies enqueue the same jobs used by manual operations.</p>
            </div>
          </div>
        </Panel>
        <Panel>
          <div className="flex items-start gap-3">
            <Play size={18} className="text-zinc-500" />
            <div>
              <div className="font-medium text-zinc-900">Approvals</div>
              <p className="mt-1 text-sm text-zinc-500">Destructive policies stop at approval with the compiled command snapshot attached.</p>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
