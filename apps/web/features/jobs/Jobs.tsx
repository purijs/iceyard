"use client";

import { Badge, Panel } from "@/components/ui";
import type { JobRead } from "@/types/api";

export function Jobs({ jobs }: { jobs: JobRead[] }) {
  return (
    <Panel title="Jobs" pad={false}>
      <table className="w-full text-sm">
        <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
          <tr>
            <th className="px-4 py-2 font-medium">Job</th>
            <th className="px-4 py-2 font-medium">Kind</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Created</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-b border-zinc-100 last:border-0">
              <td className="px-4 py-2.5 font-mono text-xs text-zinc-800">{job.id}</td>
              <td className="px-4 py-2.5 text-zinc-600">{job.kind}</td>
              <td className="px-4 py-2.5">
                <Badge tone={job.status === "queued" || job.status === "running" ? "warning" : job.status === "failed" ? "critical" : "healthy"}>{job.status}</Badge>
              </td>
              <td className="px-4 py-2.5 text-zinc-500">{new Date(job.created_at).toLocaleString()}</td>
            </tr>
          ))}
          {jobs.length === 0 ? (
            <tr>
              <td className="px-4 py-8 text-center text-zinc-400" colSpan={4}>
                No jobs yet.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </Panel>
  );
}
