"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Gauge, Sparkles, Trash2 } from "lucide-react";

import { Badge, Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import type {
  AutomationPolicy,
  ClusteringAdvice,
  CleanupPreview,
  DistributionAdvice,
  OperationDescriptor,
  ParquetAdvice,
  TableRead
} from "@/types/api";

type AdviceState = {
  clustering: ClusteringAdvice | null;
  parquet: ParquetAdvice | null;
  distribution: DistributionAdvice | null;
  cleanup: CleanupPreview | null;
};

const EMPTY_ADVICE: AdviceState = { clustering: null, parquet: null, distribution: null, cleanup: null };

export function Automation({
  token,
  tables,
  operations,
  onOpenOperation
}: {
  token: string;
  tables: TableRead[];
  operations: OperationDescriptor[];
  onOpenOperation: (operationId: string, table: TableRead) => void;
}) {
  const operationById = new Map(operations.map((operation) => [operation.id, operation]));
  const [policies, setPolicies] = useState<AutomationPolicy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<string>(tables[0]?.id ?? "");
  const [advice, setAdvice] = useState<AdviceState>(EMPTY_ADVICE);
  const [loadingAdvice, setLoadingAdvice] = useState(false);

  const selectedTable = tables.find((table) => table.id === selectedTableId) ?? null;

  const loadPolicies = useCallback(() => {
    api.policies(token).then(setPolicies).catch((err: Error) => setError(err.message));
  }, [token]);

  useEffect(() => {
    loadPolicies();
  }, [loadPolicies]);

  const opName = (id: string) => operationById.get(id)?.name ?? id;

  const loadAdvice = useCallback(async () => {
    if (!selectedTable) return;
    setLoadingAdvice(true);
    setError(null);
    try {
      const [clustering, parquet, distribution, cleanup] = await Promise.all([
        api.clusteringAdvice(token, selectedTable.id, { workload_source: "none" }),
        api.parquetAdvice(token, selectedTable.id),
        api.distributionAdvice(token, selectedTable.id),
        api.cleanupPreview(token, selectedTable.id, { time_column: "occurred_at", keep_days: 90, mode: "soft" })
      ]);
      setAdvice({ clustering, parquet, distribution, cleanup });
    } catch (err) {
      setError((err as Error).message);
      setAdvice(EMPTY_ADVICE);
    } finally {
      setLoadingAdvice(false);
    }
  }, [token, selectedTable]);

  const removePolicy = async (policyId: string) => {
    try {
      await api.deletePolicy(token, policyId);
      loadPolicies();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>
      ) : null}

      <Panel
        title="Declarative policies"
        right={<span className="text-xs text-zinc-400">{policies.length} policies · reconciled from config</span>}
        pad={false}
      >
        {policies.length === 0 ? (
          <div className="px-4 py-6 text-sm text-zinc-500">
            No policies yet. Policies are declarative (GitOps/Terraform) and bind an operation descriptor to a selector,
            trigger, and guardrails. Create one via <span className="font-mono">POST /api/v1/policies</span>.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Policy</th>
                  <th className="px-4 py-2 font-medium">Kind</th>
                  <th className="px-4 py-2 font-medium">Operation</th>
                  <th className="px-4 py-2 font-medium">Trigger</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {policies.map((policy) => (
                  <tr key={policy.id} className="border-b border-zinc-100 last:border-0">
                    <td className="px-4 py-3 font-medium text-zinc-900">{policy.name}</td>
                    <td className="px-4 py-3">
                      <Badge>{policy.kind}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-600">{opName(policy.action.op)}</td>
                    <td className="px-4 py-3 text-zinc-600">
                      {String(policy.trigger.schedule ?? policy.trigger.kind ?? "manual")}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={policy.enabled ? "healthy" : "warning"}>
                        {policy.enabled ? "enabled" : "disabled"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button onClick={() => removePolicy(policy.id)}>
                        <Trash2 size={14} /> Remove
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel
        title="Acceleration advisor"
        right={
          <div className="flex items-center gap-2">
            <select
              value={selectedTableId}
              onChange={(event) => {
                setSelectedTableId(event.target.value);
                setAdvice(EMPTY_ADVICE);
              }}
              className="rounded-md border border-zinc-300 px-2 py-1 text-sm"
            >
              {tables.map((table) => (
                <option key={table.id} value={table.id}>
                  {table.name}
                </option>
              ))}
            </select>
            <Button onClick={loadAdvice} disabled={!selectedTable || loadingAdvice}>
              <Gauge size={14} /> {loadingAdvice ? "Analyzing…" : "Analyze"}
            </Button>
          </div>
        }
      >
        {!advice.clustering && !loadingAdvice ? (
          <p className="text-sm text-zinc-500">
            Select a table and run the analysis to get clustering, Parquet, write-distribution, and retention
            recommendations derived from the layout/stats model. Each recommendation routes through the standard
            dry-run pipeline.
          </p>
        ) : null}

        {advice.clustering ? (
          <div className="grid gap-3 lg:grid-cols-2">
            <AdviceCard title="Clustering / sort" basis={advice.clustering.workload_basis}>
              {advice.clustering.recommendations.map((rec) => (
                <div key={rec.sort_order_expr} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge>{rec.strategy}</Badge>
                    <span className="font-mono text-xs text-zinc-700">{rec.sort_order_expr}</span>
                  </div>
                  <p className="text-xs text-zinc-500">{rec.rationale}</p>
                  <p className="text-xs text-zinc-500">
                    depth {rec.current_clustering_depth} → {rec.projected_clustering_depth} · projected scan ↓{" "}
                    {rec.projected_scan_reduction_pct}%
                  </p>
                  {selectedTable ? (
                    <Button onClick={() => onOpenOperation(rec.apply_operation_id, selectedTable)}>Dry run</Button>
                  ) : null}
                </div>
              ))}
              {advice.clustering.recommendations.length === 0 ? (
                <p className="text-xs text-zinc-500">No clustering change recommended.</p>
              ) : null}
            </AdviceCard>

            {advice.parquet ? (
              <AdviceCard title="Parquet tuning" basis={`current codec: ${advice.parquet.current_codec}`}>
                <p className="text-sm text-zinc-700">
                  Recommend <span className="font-mono">{advice.parquet.recommended_codec}</span> level{" "}
                  {advice.parquet.recommended_level}, dictionary {advice.parquet.dictionary_enabled ? "on" : "off"}.
                </p>
                <p className="text-xs text-zinc-500">{advice.parquet.rationale}</p>
                {selectedTable ? (
                  <Button onClick={() => onOpenOperation(advice.parquet!.apply_operation_id, selectedTable)}>
                    Apply settings
                  </Button>
                ) : null}
              </AdviceCard>
            ) : null}

            {advice.distribution ? (
              <AdviceCard title="Write distribution" basis={`current: ${advice.distribution.current_mode}`}>
                <p className="text-sm text-zinc-700">
                  Recommend <span className="font-mono">{advice.distribution.recommended_mode}</span> · projected
                  small-file reduction {advice.distribution.projected_small_file_reduction_pct}%
                </p>
                <p className="text-xs text-zinc-500">{advice.distribution.ingestion_hint}</p>
                {selectedTable ? (
                  <Button onClick={() => onOpenOperation(advice.distribution!.apply_operation_id, selectedTable)}>
                    Set mode
                  </Button>
                ) : null}
              </AdviceCard>
            ) : null}

            {advice.cleanup ? (
              <AdviceCard
                title="Retention (TTL) preview"
                basis={advice.cleanup.partition_aligned ? "partition-aligned" : "row-level"}
              >
                <p className="text-sm text-zinc-700">
                  ~{advice.cleanup.estimated_delete_pct}% would be removed past 90 days.
                </p>
                <Badge tone={advice.cleanup.guardrail_passed ? "healthy" : "critical"}>
                  guardrail {advice.cleanup.guardrail_passed ? "ok" : "blocked"}
                </Badge>
                {advice.cleanup.recommend_partitioning ? (
                  <p className="text-xs text-amber-600">Recommend partitioning by the time column for cheap TTL.</p>
                ) : null}
                {selectedTable ? (
                  <Button onClick={() => onOpenOperation(advice.cleanup!.apply_operation_id, selectedTable)}>
                    Plan cleanup
                  </Button>
                ) : null}
              </AdviceCard>
            ) : null}
          </div>
        ) : null}
      </Panel>

      <div className="grid gap-4 md:grid-cols-3">
        <InfoCard
          icon={<Sparkles size={18} className="text-zinc-500" />}
          title="Registry-driven"
          body="Every recommendation compiles to an operation descriptor and runs through the same dry-run, gate, and audit pipeline."
        />
        <InfoCard
          icon={<CalendarClock size={18} className="text-zinc-500" />}
          title="Declarative policies"
          body="Cron and threshold policies are reproducible config and enqueue the same jobs as manual operations."
        />
        <InfoCard
          icon={<Gauge size={18} className="text-zinc-500" />}
          title="Projections, not promises"
          body="What-if and advisor outputs are directional projections over indexed metadata; validate after applying."
        />
      </div>
    </div>
  );
}

function AdviceCard({ title, basis, children }: { title: string; basis: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-zinc-900">{title}</span>
        <span className="text-xs text-zinc-400">{basis}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function InfoCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <Panel>
      <div className="flex items-start gap-3">
        {icon}
        <div>
          <div className="font-medium text-zinc-900">{title}</div>
          <p className="mt-1 text-sm text-zinc-500">{body}</p>
        </div>
      </div>
    </Panel>
  );
}
