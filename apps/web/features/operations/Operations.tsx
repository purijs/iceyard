"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import type { OperationDescriptor, OperationDryRunRead, TableRead } from "@/types/api";

export function Operations({
  token,
  operations,
  selectedTable,
  openOperationId,
  onClose
}: {
  token: string;
  operations: OperationDescriptor[];
  selectedTable: TableRead | null;
  openOperationId: string | null;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState<OperationDescriptor | null>(
    openOperationId ? operations.find((operation) => operation.id === openOperationId) ?? null : null
  );
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [engine, setEngine] = useState("embedded");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [dryRun, setDryRun] = useState<OperationDryRunRead | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!openOperationId) return;
    const operation = operations.find((item) => item.id === openOperationId);
    if (!operation) return;
    setActive(operation);
    setParams(Object.fromEntries(operation.params.map((param) => [param.name, param.default ?? ""])));
    setEngine(operation.supported_engines.includes("embedded") ? "embedded" : (operation.supported_engines[0] ?? "embedded"));
    setDryRun(null);
    setMessage(null);
  }, [openOperationId, operations]);

  const filtered = useMemo(
    () => operations.filter((operation) => `${operation.name} ${operation.id} ${operation.category}`.toLowerCase().includes(query.toLowerCase())),
    [operations, query]
  );
  const groups = Array.from(new Set(filtered.map((operation) => operation.category)));
  const requiresIdempotency = active?.gates.includes("idempotent_retry") ?? false;

  async function submitDryRun() {
    if (!active) return;
    setMessage(null);
    const result = await api.dryRun(token, {
      operation_id: active.id,
      table_id: selectedTable?.id,
      engine,
      params
    });
    setDryRun(result);
    if (active.gates.includes("idempotent_retry") && !idempotencyKey) {
      setIdempotencyKey(`${active.id}-${result.id.slice(0, 8)}`);
    }
  }

  async function execute() {
    if (!dryRun) return;
    const result = await api.execute(token, {
      dry_run_id: dryRun.id,
      confirmation: dryRun.operation_id,
      idempotency_key: idempotencyKey || undefined
    });
    setMessage(result.message);
  }

  return (
    <div className="space-y-4">
      <input
        className="w-full max-w-md rounded-md border border-zinc-300 px-3 py-2 text-sm"
        placeholder="Search operations..."
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {groups.map((group) => (
        <div key={group} className="space-y-2">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-400">{group}</div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {filtered
              .filter((operation) => operation.category === group)
              .map((operation) => (
                <button
                  key={operation.id}
                  onClick={() => {
                    setActive(operation);
                    setParams(Object.fromEntries(operation.params.map((param) => [param.name, param.default ?? ""])));
                    setEngine(operation.supported_engines.includes("embedded") ? "embedded" : (operation.supported_engines[0] ?? "embedded"));
                    setIdempotencyKey("");
                    setDryRun(null);
                    setMessage(null);
                  }}
                  className="rounded-lg border border-zinc-200 bg-white p-3 text-left shadow-sm transition hover:border-zinc-400"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-zinc-900">{operation.name}</span>
                    <Badge tone={operation.safety_class === "DESTRUCTIVE" ? "critical" : operation.safety_class === "READ" ? "neutral" : "warning"}>
                      {operation.safety_class.toLowerCase()}
                    </Badge>
                  </div>
                  <div className="mt-1 font-mono text-xs text-zinc-400">{operation.id}</div>
                  <p className="mt-2 text-xs text-zinc-500">{operation.description}</p>
                </button>
              ))}
          </div>
        </div>
      ))}
      {active ? (
        <div className="fixed inset-0 z-40 flex justify-end bg-zinc-950/40" onClick={() => { setActive(null); onClose(); }}>
          <div className="flex h-full w-full max-w-xl flex-col bg-white shadow-xl" onClick={(event) => event.stopPropagation()}>
            <div className="border-b border-zinc-200 px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="font-medium text-zinc-950">{active.name}</h2>
                    <Badge tone={active.safety_class === "DESTRUCTIVE" ? "critical" : "warning"}>{active.safety_class.toLowerCase()}</Badge>
                  </div>
                  <div className="mt-1 font-mono text-xs text-zinc-400">{selectedTable?.name ?? "select a table"}</div>
                </div>
                <Button variant="ghost" onClick={() => { setActive(null); onClose(); }}>
                  Close
                </Button>
              </div>
            </div>
            <div className="flex-1 space-y-4 overflow-auto p-5">
              <Panel title="Parameters">
                <div className="space-y-3">
                  <label className="block">
                    <span className="mb-1 block font-mono text-xs text-zinc-500">engine</span>
                    <select
                      className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
                      value={engine}
                      onChange={(event) => setEngine(event.target.value)}
                    >
                      {active.supported_engines.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                  {active.params.length === 0 ? <p className="text-sm text-zinc-400">No parameters are required.</p> : null}
                  {active.params.map((param) => (
                    <label key={param.name} className="block">
                      <span className="mb-1 block font-mono text-xs text-zinc-500">{param.name}</span>
                      {param.options ? (
                        <select
                          className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
                          value={String(params[param.name] ?? param.default ?? "")}
                          onChange={(event) => setParams((current) => ({ ...current, [param.name]: event.target.value }))}
                        >
                          {param.options.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          className="w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm"
                          placeholder={param.placeholder ?? ""}
                          value={String(params[param.name] ?? "")}
                          onChange={(event) => setParams((current) => ({ ...current, [param.name]: event.target.value }))}
                        />
                      )}
                    </label>
                  ))}
                  {requiresIdempotency ? (
                    <label className="block">
                      <span className="mb-1 block font-mono text-xs text-zinc-500">idempotency_key</span>
                      <input
                        className="w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm"
                        value={idempotencyKey}
                        onChange={(event) => setIdempotencyKey(event.target.value)}
                      />
                    </label>
                  ) : null}
                </div>
              </Panel>
              {dryRun ? (
                <>
                  <Panel title="Compiled command">
                    <pre className="overflow-x-auto rounded-md bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-100">{dryRun.compiled_command}</pre>
                  </Panel>
                  <Panel title="Safety gates">
                    <div className="space-y-2">
                      {dryRun.gate_results.map((gate) => (
                        <div key={gate.id} className="flex items-start justify-between gap-3 text-sm">
                          <div>
                            <div className="font-medium text-zinc-800">{gate.label}</div>
                            <div className="text-xs text-zinc-500">{gate.detail}</div>
                          </div>
                          <Badge tone={gate.status === "blocked" ? "critical" : gate.status === "pending" ? "warning" : "healthy"}>{gate.status}</Badge>
                        </div>
                      ))}
                    </div>
                  </Panel>
                  <Panel title="Dry-run metrics">
                    <pre className="rounded-md bg-zinc-50 p-3 font-mono text-xs text-zinc-700">{JSON.stringify(dryRun.metrics, null, 2)}</pre>
                  </Panel>
                </>
              ) : null}
              {message ? <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">{message}</div> : null}
            </div>
            <div className="flex justify-end gap-2 border-t border-zinc-200 bg-zinc-50 px-5 py-3">
              <Button onClick={submitDryRun} disabled={!active.dry_run_supported}>
                Dry run
              </Button>
              <Button variant={active.safety_class === "DESTRUCTIVE" ? "danger" : "primary"} onClick={execute} disabled={!dryRun}>
                Execute
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
