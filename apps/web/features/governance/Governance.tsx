"use client";

import { Badge, Panel } from "@/components/ui";
import type { AuditEventRead } from "@/types/api";

export function Governance({ audit }: { audit: AuditEventRead[] }) {
  return (
    <div className="space-y-4">
      <Panel title="Access model">
        <div className="grid gap-2 md:grid-cols-5">
          {["platform_admin", "workspace_admin", "maintainer", "analyst", "viewer"].map((role) => (
            <div key={role} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
              <div className="font-mono text-sm text-zinc-800">{role}</div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Audit log" pad={false}>
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
            <tr>
              <th className="px-4 py-2 font-medium">Time</th>
              <th className="px-4 py-2 font-medium">Action</th>
              <th className="px-4 py-2 font-medium">Resource</th>
              <th className="px-4 py-2 font-medium">Actor</th>
            </tr>
          </thead>
          <tbody>
            {audit.map((event) => (
              <tr key={event.id} className="border-b border-zinc-100 last:border-0">
                <td className="px-4 py-2.5 text-xs text-zinc-500">{new Date(event.occurred_at).toLocaleString()}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-zinc-800">{event.action}</td>
                <td className="px-4 py-2.5">
                  <Badge>{event.resource_type}</Badge>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-zinc-500">{event.actor_id ?? "system"}</td>
              </tr>
            ))}
            {audit.length === 0 ? (
              <tr>
                <td className="px-4 py-8 text-center text-zinc-400" colSpan={4}>
                  No audit events yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
