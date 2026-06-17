"use client";

import { Play, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import type { JobLogRead, JobRead, JobRunRead, OperationDescriptor, TableRead } from "@/types/api";

export function Jobs({
  token,
  jobs,
  tables,
  operations,
  onOpenOperation,
  onRefresh
}: {
  token: string;
  jobs: JobRead[];
  tables: TableRead[];
  operations: OperationDescriptor[];
  onOpenOperation: (operationId: string, table: TableRead) => void;
  onRefresh: () => Promise<void>;
}) {
  const runnableOperations = useMemo(
    () => operations.filter((operation) => operation.dry_run_supported && operation.safety_class !== "READ"),
    [operations]
  );
  const [selectedJobId, setSelectedJobId] = useState<string | null>(jobs[0]?.id ?? null);
  const [selectedTableId, setSelectedTableId] = useState<string>(tables[0]?.id ?? "");
  const [selectedOperationId, setSelectedOperationId] = useState<string>(runnableOperations[0]?.id ?? "");
  const [runs, setRuns] = useState<JobRunRead[]>([]);
  const [logs, setLogs] = useState<JobLogRead[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedJobId && jobs[0]) setSelectedJobId(jobs[0].id);
  }, [jobs, selectedJobId]);

  useEffect(() => {
    if (!selectedOperationId && runnableOperations[0]) setSelectedOperationId(runnableOperations[0].id);
  }, [runnableOperations, selectedOperationId]);

  useEffect(() => {
    if (!selectedTableId && tables[0]) setSelectedTableId(tables[0].id);
  }, [selectedTableId, tables]);

  useEffect(() => {
    if (!selectedJobId) {
      setRuns([]);
      setLogs([]);
      return;
    }
    let cancelled = false;
    void Promise.all([api.jobRuns(token, selectedJobId), api.jobLogs(token, selectedJobId)])
      .then(([nextRuns, nextLogs]) => {
        if (!cancelled) {
          setRuns(nextRuns);
          setLogs(nextLogs);
        }
      })
      .catch((err) => {
        if (!cancelled) setMessage(err instanceof Error ? err.message : "Unable to load job detail.");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedJobId, token]);

  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;

  function startJob() {
    const table = tables.find((item) => item.id === selectedTableId);
    const operation = runnableOperations.find((item) => item.id === selectedOperationId);
    if (!table || !operation) {
      setMessage("Select a table and operation first.");
      return;
    }
    onOpenOperation(operation.id, table);
  }

  async function cancelJob() {
    if (!selectedJob) return;
    setMessage(null);
    try {
      await api.cancelJob(token, selectedJob.id);
      await onRefresh();
      setMessage("Job cancelled.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to cancel job.");
    }
  }

  return (
    <div className="space-y-4">
      <Panel title="Start job">
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-500">Table</span>
            <select className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm" value={selectedTableId} onChange={(event) => setSelectedTableId(event.target.value)}>
              {tables.map((table) => (
                <option key={table.id} value={table.id}>
                  {table.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-500">Operation</span>
            <select className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm" value={selectedOperationId} onChange={(event) => setSelectedOperationId(event.target.value)}>
              {runnableOperations.map((operation) => (
                <option key={operation.id} value={operation.id}>
                  {operation.name}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end">
            <Button onClick={startJob} variant="primary">
              <span className="inline-flex items-center gap-2">
                <Play size={15} />
                Configure & dry run
              </span>
            </Button>
          </div>
        </div>
      </Panel>

      <Panel title="Jobs" pad={false}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-medium">Job</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Started</th>
                <th className="px-4 py-2 font-medium">Updated</th>
                <th className="px-4 py-2 font-medium">Request</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => setSelectedJobId(job.id)}
                  className={`cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-zinc-50 ${selectedJobId === job.id ? "bg-zinc-50" : ""}`}
                >
                  <td className="px-4 py-3 font-mono text-xs text-zinc-800">{shortId(job.id)}</td>
                  <td className="px-4 py-3 text-zinc-600">{job.kind}</td>
                  <td className="px-4 py-3">
                    <Badge tone={jobTone(job.status)}>{job.status}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-500">{formatTime(job.created_at)}</td>
                  <td className="px-4 py-3 font-mono text-zinc-500">{formatDuration(job.created_at, job.updated_at)}</td>
                  <td className="px-4 py-3 font-mono text-xs text-zinc-400">{job.operation_request_id ? shortId(job.operation_request_id) : "manual"}</td>
                </tr>
              ))}
              {jobs.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-zinc-400" colSpan={6}>
                    No jobs yet. Start one from a table maintenance card or the selector above.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Panel>

      {selectedJob ? (
        <Panel
          title={<span className="font-mono">{shortId(selectedJob.id)}</span>}
          right={
            selectedJob.status === "queued" || selectedJob.status === "running" ? (
              <Button onClick={cancelJob} variant="ghost">
                <span className="inline-flex items-center gap-2">
                  <X size={15} />
                  Cancel
                </span>
              </Button>
            ) : null
          }
        >
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">Pipeline</div>
              <div className="space-y-2 text-sm">
                {["Plan rewrite", "Rewrite data files", "Rewrite manifests", "Commit snapshot", "Verify & release restore point"].map((step, index) => (
                  <div key={step} className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${index === 0 ? "bg-emerald-500" : index === 1 && selectedJob.status !== "queued" ? "bg-amber-500" : "border border-zinc-300 bg-white"}`} />
                    <span className={index > 1 ? "text-zinc-400" : "text-zinc-700"}>{step}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">Runs</div>
              <div className="space-y-2">
                {runs.map((run) => (
                  <div key={run.id} className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-mono">{shortId(run.id)}</span>
                      <Badge tone={jobTone(run.status)}>{run.status}</Badge>
                    </div>
                    <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap font-mono text-xs text-zinc-600">{run.compiled_command}</pre>
                  </div>
                ))}
                {!runs.length ? <div className="text-sm text-zinc-400">No runs recorded.</div> : null}
              </div>
            </div>
          </div>
        </Panel>
      ) : null}

      <Panel title="Logs" pad={false}>
        <div className="max-h-64 overflow-auto bg-zinc-950 p-4 font-mono text-xs leading-relaxed text-zinc-100">
          {logs.map((log) => (
            <div key={log.id}>
              <span className="text-zinc-500">{formatTime(log.created_at)}</span> <span className="text-zinc-400">{log.level}</span> {log.message}
            </div>
          ))}
          {!logs.length ? <div className="text-zinc-500">No logs selected.</div> : null}
        </div>
      </Panel>

      {message ? <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">{message}</div> : null}
    </div>
  );
}

function jobTone(status: string): "healthy" | "warning" | "critical" {
  if (status === "failed" || status === "blocked") return "critical";
  if (status === "queued" || status === "running" || status === "pending") return "warning";
  return "healthy";
}

function shortId(id: string) {
  return id.slice(0, 8);
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDuration(start: string, end: string) {
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) return "-";
  const seconds = Math.max(0, Math.round((endMs - startMs) / 1000));
  return `00:${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
