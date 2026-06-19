"use client";

import { X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import type { ControlContext } from "@/app/page";
import { api } from "@/lib/api";
import type { JobLogRead, JobRead, JobRunRead } from "@/types/api";

type JobTab = "active" | "queued" | "completed" | "failed" | "all";

export function Jobs({
  token,
  jobs,
  context,
  onRefresh
}: {
  token: string;
  jobs: JobRead[];
  context: ControlContext;
  onRefresh: () => Promise<void>;
}) {
  const [tab, setTab] = useState<JobTab>("active");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(jobs[0]?.id ?? null);
  const [runs, setRuns] = useState<JobRunRead[]>([]);
  const [logs, setLogs] = useState<JobLogRead[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const filteredJobs = useMemo(() => jobs.filter((job) => matchesTab(job, tab)), [jobs, tab]);

  useEffect(() => {
    if (!selectedJobId || !jobs.some((job) => job.id === selectedJobId)) {
      setSelectedJobId(filteredJobs[0]?.id ?? jobs[0]?.id ?? null);
    }
  }, [filteredJobs, jobs, selectedJobId]);

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
      <Panel
        title="Jobs"
        right={<span className="text-xs text-zinc-400">{context.label} · jobs are created from dry-run/execute flows</span>}
        pad={false}
      >
        <div className="flex flex-wrap gap-2 border-b border-zinc-200 p-3">
          {[
            ["active", "Running"],
            ["queued", "Queued"],
            ["completed", "Completed"],
            ["failed", "Failed"],
            ["all", "All"]
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key as JobTab)}
              className={`rounded-md px-3 py-1.5 text-sm ${tab === key ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"}`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-medium">Job</th>
                <th className="px-4 py-2 font-medium">Operation</th>
                <th className="px-4 py-2 font-medium">Target</th>
                <th className="px-4 py-2 font-medium">Runtime</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => setSelectedJobId(job.id)}
                  className={`cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-zinc-50 ${selectedJobId === job.id ? "bg-zinc-50" : ""}`}
                >
                  <td className="px-4 py-3 font-mono text-xs text-zinc-800">{shortId(job.id)}</td>
                  <td className="px-4 py-3 font-mono text-xs text-zinc-700">{job.operation_id ?? job.kind}</td>
                  <td className="px-4 py-3 font-mono text-xs text-zinc-600">{job.table_name ?? "catalog scope"}</td>
                  <td className="px-4 py-3">
                    <Badge tone={runtimeTone(job)}>{runtimeLabel(job)}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={jobTone(job.status)}>{job.status}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-500">{formatTime(job.created_at)}</td>
                  <td className="px-4 py-3 font-mono text-zinc-500">{formatDuration(job.created_at, job.updated_at)}</td>
                </tr>
              ))}
              {!filteredJobs.length ? (
                <tr>
                  <td className="px-4 py-8 text-center text-zinc-400" colSpan={7}>
                    No jobs in this view. Jobs appear here after an operation is executed or an approval creates work.
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
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">Job context</div>
              <dl className="space-y-2 text-sm">
                <KeyValue label="Operation" value={selectedJob.operation_id ?? selectedJob.kind} />
                <KeyValue label="Target" value={selectedJob.table_name ?? "catalog scope"} />
                <KeyValue label="Runtime" value={runs[0]?.engine ?? runtimeLabel(selectedJob)} />
                <KeyValue label="Restore point" value={runs.find((run) => run.pre_op_restore_ref)?.pre_op_restore_ref ?? "none"} />
                <KeyValue label="Correlation" value={selectedJob.correlation_id ?? "none"} />
              </dl>
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

function matchesTab(job: JobRead, tab: JobTab) {
  if (tab === "all") return true;
  if (tab === "active") return job.status === "running";
  if (tab === "completed") return job.status === "succeeded" || job.status === "cancelled";
  if (tab === "failed") return job.status === "failed" || job.status === "blocked";
  return job.status === tab;
}

function jobTone(status: string): "healthy" | "warning" | "critical" | "neutral" {
  if (status === "failed" || status === "blocked") return "critical";
  if (status === "queued" || status === "running" || status === "pending") return "warning";
  if (status === "cancelled") return "neutral";
  return "healthy";
}

function runtimeLabel(job: JobRead) {
  if (!job.operation_id) return "Internal worker";
  if (job.operation_id.includes("rewrite") || job.operation_id.includes("compact")) return "Requires compute backend";
  if (job.catalog_connection_id) return "Native catalog";
  return "Internal worker";
}

function runtimeTone(job: JobRead): "healthy" | "warning" | "neutral" {
  return runtimeLabel(job) === "Requires compute backend" ? "warning" : "healthy";
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="max-w-[26rem] truncate font-mono text-zinc-900">{value}</dd>
    </div>
  );
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
