"use client";

import { Play, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import type { OperationDescriptor, OperationDryRunRead, TableRead } from "@/types/api";

type OperationParam = OperationDescriptor["params"][number];

export function Operations({
  token,
  operations,
  selectedTable,
  openOperationId,
  onClose,
  onExecuted
}: {
  token: string;
  operations: OperationDescriptor[];
  selectedTable: TableRead | null;
  openOperationId: string | null;
  onClose: () => void;
  onExecuted?: () => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [safetyFilter, setSafetyFilter] = useState("all");
  const [engineFilter, setEngineFilter] = useState("all");
  const [active, setActive] = useState<OperationDescriptor | null>(null);
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [engine, setEngine] = useState("embedded");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [dryRun, setDryRun] = useState<OperationDryRunRead | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (!openOperationId) return;
    const operation = operations.find((item) => item.id === openOperationId);
    if (!operation) return;
    setActive(operation);
    setParams(defaultParams(operation));
    setEngine(operation.supported_engines.includes("embedded") ? "embedded" : (operation.supported_engines[0] ?? "embedded"));
    setIdempotencyKey("");
    setDryRun(null);
    setMessage(null);
    setShowAdvanced(false);
  }, [openOperationId, operations]);

  const filtered = useMemo(
    () =>
      operations.filter((operation) => {
        const matchesQuery = `${operation.name} ${operation.id} ${operation.category}`.toLowerCase().includes(query.toLowerCase());
        const matchesSafety = safetyFilter === "all" || operation.safety_class === safetyFilter;
        const matchesEngine = engineFilter === "all" || operation.supported_engines.includes(engineFilter);
        return matchesQuery && matchesSafety && matchesEngine;
      }),
    [engineFilter, operations, query, safetyFilter]
  );
  const groups = Array.from(new Set(filtered.map((operation) => operation.category)));
  const requiresIdempotency = active?.gates.includes("idempotent_retry") ?? false;
  const normalParams = active?.params.filter((param) => !param.advanced && isVisibleParam(param, params)) ?? [];
  const advancedParams = active?.params.filter((param) => param.advanced && isVisibleParam(param, params)) ?? [];

  function openOperation(operation: OperationDescriptor) {
    setActive(operation);
    setParams(defaultParams(operation));
    setEngine(operation.supported_engines.includes("embedded") ? "embedded" : (operation.supported_engines[0] ?? "embedded"));
    setIdempotencyKey("");
    setDryRun(null);
    setMessage(null);
    setShowAdvanced(false);
  }

  async function submitDryRun() {
    if (!active) return;
    setMessage(null);
    try {
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
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Dry-run failed.");
    }
  }

  async function execute() {
    if (!dryRun) return;
    setMessage(null);
    try {
      const result = await api.execute(token, {
        dry_run_id: dryRun.id,
        confirmation: dryRun.operation_id,
        idempotency_key: idempotencyKey || undefined
      });
      setMessage(result.message);
      if (result.job_id && onExecuted) {
        await onExecuted();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Execution request failed.");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          className="w-full max-w-md rounded-md border border-zinc-300 px-3 py-2 text-sm"
          placeholder="Search operations..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Segmented
          value={safetyFilter}
          items={[
            ["all", "All"],
            ["READ", "read"],
            ["METADATA", "metadata"],
            ["WRITE", "write"],
            ["REWRITE", "rewrite"],
            ["DESTRUCTIVE", "destructive"],
            ["MIGRATION_ADMIN", "migration"]
          ]}
          onChange={setSafetyFilter}
        />
        <Segmented
          value={engineFilter}
          items={[
            ["all", "All engines"],
            ["spark", "Spark"],
            ["trino", "Trino"],
            ["flink", "Flink"],
            ["embedded", "Embedded"]
          ]}
          onChange={setEngineFilter}
        />
        <div className="ml-auto text-xs text-zinc-400">{filtered.length} operations</div>
      </div>

      <Panel>
        <p className="text-sm text-zinc-500">
          Operation descriptors drive the command palette, generated forms, SQL preview, dry-run, safety gates, approvals, jobs, and scheduling.
        </p>
      </Panel>

      {groups.map((group) => {
        const items = filtered.filter((operation) => operation.category === group);
        return (
          <div key={group} className="space-y-2">
            <div className="text-xs font-medium uppercase tracking-wide text-zinc-400">
              {group} - {items.length}
            </div>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {items.map((operation) => (
                <button
                  key={operation.id}
                  onClick={() => openOperation(operation)}
                  className="rounded-lg border border-zinc-200 bg-white p-3 text-left shadow-sm transition hover:border-zinc-400"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-zinc-900">{operation.name}</span>
                    <Badge tone={safetyTone(operation.safety_class)}>{safetyLabel(operation.safety_class)}</Badge>
                  </div>
                  <div className="mt-1 font-mono text-xs text-zinc-400">{operation.id}</div>
                  <p className="mt-2 text-xs text-zinc-500">{operation.description}</p>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {operation.supported_engines.map((item) => (
                      <span key={item} className="rounded border border-zinc-200 px-1 py-0.5 font-mono text-[11px] text-zinc-400">
                        {item}
                      </span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </div>
        );
      })}

      {active ? (
        <div className="fixed inset-0 z-40 flex justify-end bg-zinc-950/40" onClick={() => { setActive(null); onClose(); }}>
          <div className="flex h-full w-full max-w-xl flex-col bg-white shadow-xl" onClick={(event) => event.stopPropagation()}>
            <div className="border-b border-zinc-200 px-5 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-medium text-zinc-950">{active.name}</h2>
                    <Badge tone={safetyTone(active.safety_class)}>{safetyLabel(active.safety_class)}</Badge>
                  </div>
                  <div className="mt-1 font-mono text-xs text-zinc-400">{selectedTable?.name ?? "no table selected"}</div>
                </div>
                <button className="rounded-md p-1 text-zinc-400 hover:bg-zinc-100" onClick={() => { setActive(null); onClose(); }}>
                  <X size={16} />
                </button>
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
                  {normalParams.map((param) => (
                    <ParamField
                      key={param.name}
                      param={param}
                      value={params[param.name]}
                      onChange={(value) => setParams((current) => ({ ...current, [param.name]: value }))}
                    />
                  ))}
                  {advancedParams.length ? (
                    <div className="rounded-md border border-zinc-200">
                      <button
                        onClick={() => setShowAdvanced((current) => !current)}
                        className="flex w-full items-center justify-between px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50"
                      >
                        <span>Advanced parameters</span>
                        <span className="font-mono text-xs text-zinc-400">{advancedParams.length}</span>
                      </button>
                      {showAdvanced ? (
                        <div className="space-y-3 border-t border-zinc-200 p-3">
                          {advancedParams.map((param) => (
                            <ParamField
                              key={param.name}
                              param={param}
                              value={params[param.name]}
                              onChange={(value) => setParams((current) => ({ ...current, [param.name]: value }))}
                            />
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
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
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-100">{dryRun.compiled_command}</pre>
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
              ) : (
                <Panel title="SQL template">
                  <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-zinc-50 p-3 font-mono text-xs leading-relaxed text-zinc-700">{active.sql_template}</pre>
                </Panel>
              )}

              {message ? <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">{message}</div> : null}
            </div>

            <div className="flex justify-end gap-2 border-t border-zinc-200 bg-zinc-50 px-5 py-3">
              <Button onClick={submitDryRun} disabled={!active.dry_run_supported}>
                <span className="inline-flex items-center gap-2">
                  <Play size={15} />
                  Dry run
                </span>
              </Button>
              <Button variant={active.safety_class === "DESTRUCTIVE" ? "danger" : "primary"} onClick={execute} disabled={!dryRun}>
                {active.approval_required ? "Request approval" : "Queue job"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Segmented({
  value,
  items,
  onChange
}: {
  value: string;
  items: Array<[string, string]>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex rounded-md border border-zinc-300 bg-white p-0.5 text-xs">
      {items.map(([key, label]) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`rounded px-2 py-1 ${value === key ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function ParamField({
  param,
  value,
  onChange
}: {
  param: OperationParam;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-xs text-zinc-500">
        {param.name}
        {param.required ? " *" : ""}
      </span>
      {param.options ? (
        <select
          className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm"
          value={String(value ?? param.default ?? "")}
          onChange={(event) => onChange(event.target.value)}
        >
          {param.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ) : param.type === "boolean" || param.type === "bool" ? (
        <button
          type="button"
          onClick={() => onChange(!(value === true || value === "true"))}
          className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${value === true || value === "true" ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-300 bg-white text-zinc-700"}`}
        >
          <span className={`h-2 w-2 rounded-full ${value === true || value === "true" ? "bg-white" : "bg-zinc-300"}`} />
          {value === true || value === "true" ? "true" : "false"}
        </button>
      ) : (
        <input
          className="w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm"
          placeholder={param.placeholder ?? ""}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}

function defaultParams(operation: OperationDescriptor) {
  return Object.fromEntries(
    operation.params.map((param) => [
      param.name,
      param.default ?? (param.type === "boolean" || param.type === "bool" ? false : "")
    ])
  );
}

function isVisibleParam(param: OperationParam, params: Record<string, unknown>) {
  if (!param.show_if) return true;
  const field = String(param.show_if.field ?? "");
  const expected = param.show_if.eq;
  return params[field] === expected;
}

function safetyTone(safetyClass: OperationDescriptor["safety_class"]) {
  if (safetyClass === "DESTRUCTIVE") return "critical";
  if (safetyClass === "READ" || safetyClass === "METADATA" || safetyClass === "MIGRATION_ADMIN") return "neutral";
  return "warning";
}

function safetyLabel(safetyClass: OperationDescriptor["safety_class"]) {
  if (safetyClass === "MIGRATION_ADMIN") return "migration";
  return safetyClass.toLowerCase();
}
