"use client";

import { Download } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import type { ControlContext } from "@/app/page";
import { api } from "@/lib/api";
import type { ApprovalRead, AuditEventRead, OperationDescriptor, RoleRead } from "@/types/api";

type GovernanceTab = "access" | "approvals" | "audit";

export function Governance({
  token,
  roles,
  audit,
  approvals,
  operations,
  context,
  onRefresh
}: {
  token: string;
  roles: RoleRead[];
  audit: AuditEventRead[];
  approvals: ApprovalRead[];
  operations: OperationDescriptor[];
  context: ControlContext;
  onRefresh: () => Promise<void>;
}) {
  const [tab, setTab] = useState<GovernanceTab>("access");
  const [message, setMessage] = useState<string | null>(null);
  const scopedAudit = useMemo(() => audit.filter((event) => matchesContext(event, context)), [audit, context]);
  const pendingApprovals = approvals.filter((approval) => approval.status === "pending");

  async function decide(approvalId: string, decision: "approved" | "rejected") {
    setMessage(null);
    try {
      await api.decideApproval(token, approvalId, {
        decision,
        reason: decision === "approved" ? "Approved from governance review." : "Rejected from governance review."
      });
      await onRefresh();
      setMessage(`Approval ${decision}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to update approval.");
    }
  }

  function exportAudit() {
    const blob = new Blob([JSON.stringify(scopedAudit, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "iceyard-audit-log.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-6 overflow-x-auto border-b border-zinc-200">
        {[
          ["access", "Access"],
          ["approvals", "Approvals"],
          ["audit", "Audit Log"]
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key as GovernanceTab)}
            className={`shrink-0 border-b-2 px-1 pb-2 text-sm ${tab === key ? "border-zinc-950 font-medium text-zinc-950" : "border-transparent text-zinc-500 hover:text-zinc-900"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {message ? <div className="rounded-md border border-zinc-200 bg-white p-3 text-sm text-zinc-700">{message}</div> : null}

      {tab === "access" ? (
        <div className="space-y-4">
          <Panel
            title="Roles & permissions"
            right={<span className="text-xs text-zinc-400">operation-level permissions · scope {context.label}</span>}
            pad={false}
          >
            <table className="w-full min-w-[760px] text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Role</th>
                  <th className="px-4 py-2 font-medium">Granted operations</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => (
                  <tr key={role.id} className="border-b border-zinc-100 last:border-0">
                    <td className="px-4 py-3 font-medium text-zinc-900">{role.name}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {role.permissions.map((permission) => (
                          <Badge key={permission.id}>{permission.action}</Badge>
                        ))}
                        {!role.permissions.length ? <span className="text-zinc-400">No permissions</span> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <ApprovalPolicy operations={operations} />
        </div>
      ) : null}

      {tab === "approvals" ? (
        <Panel title="Pending approvals" right={<Badge tone={pendingApprovals.length ? "warning" : "neutral"}>{pendingApprovals.length} pending</Badge>}>
          <div className="space-y-3">
            {pendingApprovals.map((approval) => (
              <div key={approval.id} className="rounded-md border border-zinc-200 p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-zinc-900">Operation request</div>
                    <div className="mt-1 font-mono text-xs text-zinc-500">{approval.operation_request_id}</div>
                    <div className="mt-1 text-xs text-zinc-400">
                      requested by {approval.requested_by ?? "system"} · {formatDate(approval.created_at)}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={() => void decide(approval.id, "rejected")}>Reject</Button>
                    <Button variant="primary" onClick={() => void decide(approval.id, "approved")}>
                      Approve
                    </Button>
                  </div>
                </div>
                <pre className="mt-3 overflow-x-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs text-zinc-700">{approval.compiled_command_snapshot}</pre>
                <p className="mt-2 text-xs text-zinc-400">The compiled command is snapshotted with the request; approving runs this exact request.</p>
              </div>
            ))}
            {!pendingApprovals.length ? <div className="py-8 text-center text-sm text-zinc-400">No pending approvals.</div> : null}
          </div>
        </Panel>
      ) : null}

      {tab === "audit" ? (
        <Panel
          title="Audit log"
          right={
            <Button onClick={exportAudit}>
              <Download size={15} />
              Export to SIEM
            </Button>
          }
          pad={false}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Time</th>
                  <th className="px-4 py-2 font-medium">Actor</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Resource</th>
                  <th className="px-4 py-2 font-medium">Executed as / context</th>
                  <th className="px-4 py-2 font-medium">Approval</th>
                </tr>
              </thead>
              <tbody>
                {scopedAudit.map((event) => (
                  <tr key={event.id} className="border-b border-zinc-100 last:border-0">
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{formatDate(event.occurred_at)}</td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-700">{event.actor_id ?? "system"}</td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-900">{event.action}</td>
                    <td className="px-4 py-3">
                      <div className="font-mono text-xs text-zinc-700">{event.resource_type}</div>
                      <div className="font-mono text-xs text-zinc-400">{event.resource_id ?? "-"}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{runtimeContext(event, context)}</td>
                    <td className="px-4 py-3 text-zinc-600">{approvalLabel(event)}</td>
                  </tr>
                ))}
                {!scopedAudit.length ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-zinc-400" colSpan={6}>
                      No audit events in this context.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}

function ApprovalPolicy({ operations }: { operations: OperationDescriptor[] }) {
  const rows = approvalPolicyRows(operations);
  return (
    <Panel title="Approval policy" right={<span className="text-xs text-zinc-400">derived from operation descriptors</span>} pad={false}>
      <table className="w-full min-w-[820px] text-sm">
        <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
          <tr>
            <th className="px-4 py-2 font-medium">Scope</th>
            <th className="px-4 py-2 font-medium">When approval is required</th>
            <th className="px-4 py-2 font-medium">Operations</th>
            <th className="px-4 py-2 font-medium">Gates</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.scope} className="border-b border-zinc-100 last:border-0">
              <td className="px-4 py-3 font-medium text-zinc-900">{row.scope}</td>
              <td className="px-4 py-3 text-zinc-600">{row.reason}</td>
              <td className="px-4 py-3 text-zinc-600">{row.count} configured</td>
              <td className="px-4 py-3 font-mono text-xs text-zinc-500">{row.gates.join(", ") || "descriptor approval flag"}</td>
            </tr>
          ))}
          {!rows.length ? (
            <tr>
              <td className="px-4 py-8 text-center text-zinc-400" colSpan={4}>
                No approval-required operations are loaded.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </Panel>
  );
}

function approvalPolicyRows(operations: OperationDescriptor[]) {
  const approvalRequired = operations.filter(
    (operation) => operation.approval_required || operation.gates.some((gate) => gate.includes("approval"))
  );
  const groups = new Map<string, OperationDescriptor[]>();
  for (const operation of approvalRequired) {
    const scope = approvalScope(operation);
    groups.set(scope, [...(groups.get(scope) ?? []), operation]);
  }
  return Array.from(groups.entries()).map(([scope, grouped]) => ({
    scope,
    reason: approvalReason(scope),
    count: grouped.length,
    gates: Array.from(new Set(grouped.flatMap((operation) => operation.gates.filter((gate) => gate.includes("approval"))))).sort()
  }));
}

function approvalScope(operation: OperationDescriptor) {
  if (operation.safety_class === "DESTRUCTIVE") return "Destructive changes";
  if (operation.safety_class === "REWRITE") return "Data rewrites";
  if (operation.category === "Retention") return "Retention";
  if (operation.category === "Time travel" || operation.category === "Snapshots") return "Snapshots";
  if (operation.category === "Schema") return "Schema";
  return operation.category;
}

function approvalReason(scope: string) {
  const reasons: Record<string, string> = {
    "Destructive changes": "Drop, purge, or irreversible operations require explicit review.",
    "Data rewrites": "Maintenance that rewrites data files requires a dry-run and review before execution.",
    Retention: "Snapshot expiry and orphan cleanup require retention/path gates before execution.",
    Snapshots: "Rollback, cherry-pick, and ref movement require review when protected.",
    Schema: "Potential reader-impacting schema changes require review."
  };
  return reasons[scope] ?? "Descriptor declares an approval gate.";
}

function matchesContext(event: AuditEventRead, context: ControlContext) {
  if (context.isAll) return true;
  if (event.resource_type === "environment" && event.resource_id === context.environmentId) return true;
  if (event.resource_type === "catalog_connection" && event.resource_id === context.catalogConnectionId) return true;
  const state = { ...(event.before_state ?? {}), ...(event.after_state ?? {}), ...(event.event_metadata ?? {}) };
  if (state.environment_id && state.environment_id === context.environmentId) return true;
  if (state.catalog_connection_id && state.catalog_connection_id === context.catalogConnectionId) return true;
  return ["auth.", "roles.", "approval.", "users."].some((prefix) => event.action.startsWith(prefix));
}

function runtimeContext(event: AuditEventRead, context: ControlContext) {
  const state = { ...(event.after_state ?? {}), ...(event.event_metadata ?? {}) };
  if (typeof state.engine === "string") return state.engine;
  if (typeof state.runtime === "string") return state.runtime;
  if (context.catalogConnection) return `${context.catalogConnection.name} (${context.catalogConnection.catalog_type})`;
  return "control plane";
}

function approvalLabel(event: AuditEventRead) {
  if (event.action.startsWith("approval.")) return event.action.replace("approval.", "");
  if (event.action.includes("blocked")) return "hard-gate";
  return "auto";
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
