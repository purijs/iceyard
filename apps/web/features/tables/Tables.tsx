"use client";

import {
  ChevronLeft,
  Database,
  Eye,
  GitBranch,
  Lock,
  Play,
  RotateCcw,
  Search,
  Settings,
  Tag,
  Table2,
  Wrench
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, formatBytes, Panel, toneForScore } from "@/components/ui";
import { api } from "@/lib/api";
import type {
  EnvironmentRead,
  HealthRead,
  OperationDescriptor,
  PartitionSpecRead,
  SchemaVersionRead,
  SnapshotRead,
  SortOrderRead,
  TablePreviewRead,
  TableRead,
  TableRefRead
} from "@/types/api";

type DetailTab = "overview" | "schema" | "partitions" | "snapshots" | "refs" | "maintenance" | "preview" | "settings";

const DETAIL_TABS: Array<[DetailTab, string]> = [
  ["overview", "Overview"],
  ["schema", "Schema"],
  ["partitions", "Partitions"],
  ["snapshots", "Snapshots"],
  ["refs", "Branches & Tags"],
  ["maintenance", "Maintenance"],
  ["preview", "Preview"],
  ["settings", "Settings"]
];

const PREVIEW_RESOURCES = ["rows", "files", "manifests", "snapshots", "partitions", "refs", "position_deletes"];

const MAINTENANCE_CARDS = [
  {
    id: "rewrite_data_files",
    title: "Compaction",
    body: "Bin-pack small files to 512 MB",
    recommended: true
  },
  {
    id: "rewrite_data_files",
    title: "Sort / Z-order",
    body: "Restore clustering for pruning",
    recommended: false
  },
  {
    id: "rewrite_manifests",
    title: "Rewrite manifests",
    body: "Consolidate manifest files",
    recommended: true
  },
  {
    id: "rewrite_position_deletes",
    title: "Rewrite delete files",
    body: "Compact position/equality deletes",
    recommended: false
  },
  {
    id: "expire_snapshots",
    title: "Expire snapshots",
    body: "Bound metadata growth",
    recommended: false,
    gated: true
  },
  {
    id: "remove_orphan_files",
    title: "Remove orphan files",
    body: "Delete unreferenced files",
    recommended: false,
    gated: true
  }
];

type DetailState = {
  snapshots: SnapshotRead[];
  refs: TableRefRead[];
  schemas: SchemaVersionRead[];
  partitions: PartitionSpecRead[];
  sortOrders: SortOrderRead[];
};

const EMPTY_DETAIL: DetailState = {
  snapshots: [],
  refs: [],
  schemas: [],
  partitions: [],
  sortOrders: []
};

export function Tables({
  token,
  tables,
  environments,
  selected,
  health,
  operations,
  onSelect,
  onOpenOperation
}: {
  token: string;
  tables: TableRead[];
  environments: EnvironmentRead[];
  selected: TableRead | null;
  health: HealthRead | null;
  operations: OperationDescriptor[];
  onSelect: (table: TableRead | null) => void;
  onOpenOperation: (operationId: string, table: TableRead) => void;
}) {
  const [query, setQuery] = useState("");
  const [healthFilter, setHealthFilter] = useState<"all" | "healthy" | "warning" | "critical">("all");
  const envById = useMemo(() => new Map(environments.map((env) => [env.id, env.name])), [environments]);
  const namespaceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const table of tables) {
      counts.set(namespaceOf(table.name), (counts.get(namespaceOf(table.name)) ?? 0) + 1);
    }
    return Array.from(counts.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [tables]);

  const filtered = tables.filter((table) => {
    const matchesQuery = table.name.toLowerCase().includes(query.toLowerCase());
    const tone = toneForScore(table.health_score);
    return matchesQuery && (healthFilter === "all" || tone === healthFilter);
  });

  if (selected) {
    return (
      <TableDetail
        token={token}
        table={selected}
        envName={envById.get(selected.environment_id) ?? "env"}
        health={health}
        operations={operations}
        onBack={() => onSelect(null)}
        onOpenOperation={onOpenOperation}
      />
    );
  }

  return (
    <div className="space-y-4">
      <Panel title="Namespaces" pad={false}>
        <div className="space-y-1 p-3 text-sm">
          <div className="flex items-center justify-between rounded-md bg-zinc-100 px-3 py-2 font-medium text-zinc-900">
            <span className="flex items-center gap-2">
              <Database size={15} />
              All namespaces
            </span>
            <span className="font-mono text-xs text-zinc-500">{tables.length}</span>
          </div>
          {namespaceCounts.map(([namespace, count]) => (
            <div key={namespace} className="flex items-center justify-between px-3 py-2 text-zinc-600">
              <span className="font-mono">{namespace}</span>
              <span className="font-mono text-xs text-zinc-400">{count}</span>
            </div>
          ))}
        </div>
      </Panel>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex w-full max-w-sm items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 py-2">
          <Search size={15} className="text-zinc-400" />
          <input
            className="w-full bg-transparent text-sm outline-none placeholder:text-zinc-400"
            placeholder="Filter tables..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <Segmented
          value={healthFilter}
          items={[
            ["all", "All"],
            ["healthy", "Healthy"],
            ["warning", "Warning"],
            ["critical", "Critical"]
          ]}
          onChange={(value) => setHealthFilter(value as typeof healthFilter)}
        />
        <div className="ml-auto text-xs text-zinc-400">{filtered.length} tables</div>
      </div>

      <Panel pad={false}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-medium">Table</th>
                <th className="px-4 py-2 font-medium">Env</th>
                <th className="px-4 py-2 font-medium">Fmt</th>
                <th className="px-4 py-2 font-medium">Health</th>
                <th className="px-4 py-2 font-medium">Files</th>
                <th className="px-4 py-2 font-medium">Small-file</th>
                <th className="px-4 py-2 font-medium">Deletes</th>
                <th className="px-4 py-2 font-medium">Snaps</th>
                <th className="px-4 py-2 font-medium">Size</th>
                <th className="px-4 py-2 font-medium">Last compaction</th>
                <th className="px-4 py-2 font-medium">Owner</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((table) => (
                <tr
                  key={table.id}
                  onClick={() => onSelect(table)}
                  className="cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-zinc-50"
                >
                  <td className="px-4 py-3 font-mono text-zinc-900">{table.name}</td>
                  <td className="px-4 py-3">
                    <Badge>{envById.get(table.environment_id) ?? "env"}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge>v{table.format_version}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={toneForScore(table.health_score)}>{table.health_score}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono">{table.metrics?.file_count.toLocaleString()}</td>
                  <td className="px-4 py-3 font-mono">{table.metrics?.small_file_ratio.toFixed(2)}</td>
                  <td className="px-4 py-3 font-mono">{table.metrics?.delete_file_count.toLocaleString()}</td>
                  <td className="px-4 py-3 font-mono">{table.metrics?.snapshot_count.toLocaleString()}</td>
                  <td className="px-4 py-3 font-mono">{formatBytes(table.metrics?.data_size_bytes ?? 0)}</td>
                  <td className="px-4 py-3 text-zinc-600">{relativeDate(table.metrics?.last_compaction_at)}</td>
                  <td className="px-4 py-3 text-zinc-600">{table.owner ?? <span className="text-amber-700">unassigned</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function TableDetail({
  token,
  table,
  envName,
  health,
  operations,
  onBack,
  onOpenOperation
}: {
  token: string;
  table: TableRead;
  envName: string;
  health: HealthRead | null;
  operations: OperationDescriptor[];
  onBack: () => void;
  onOpenOperation: (operationId: string, table: TableRead) => void;
}) {
  const [tab, setTab] = useState<DetailTab>("overview");
  const [detail, setDetail] = useState<DetailState>(EMPTY_DETAIL);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [previewResource, setPreviewResource] = useState("rows");
  const [preview, setPreview] = useState<TablePreviewRead | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(EMPTY_DETAIL);
    setDetailError(null);
    void Promise.all([
      api.tableSnapshots(token, table.id),
      api.tableRefs(token, table.id),
      api.tableSchema(token, table.id),
      api.tablePartitions(token, table.id),
      api.tableSortOrders(token, table.id)
    ])
      .then(([snapshots, refs, schemas, partitions, sortOrders]) => {
        if (!cancelled) setDetail({ snapshots, refs, schemas, partitions, sortOrders });
      })
      .catch((err) => {
        if (!cancelled) setDetailError(err instanceof Error ? err.message : "Unable to load table detail.");
      });
    return () => {
      cancelled = true;
    };
  }, [table.id, token]);

  useEffect(() => {
    if (tab !== "preview") return;
    let cancelled = false;
    setPreviewError(null);
    void api
      .tablePreview(token, table.id, previewResource)
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch((err) => {
        if (!cancelled) setPreviewError(err instanceof Error ? err.message : "Unable to load preview.");
      });
    return () => {
      cancelled = true;
    };
  }, [previewResource, tab, table.id, token]);

  const latestSchema = detail.schemas.at(-1);
  const schemaFields = asRecords(latestSchema?.table_schema.fields);
  const currentPartition = detail.partitions.find((partition) => partition.is_current) ?? detail.partitions[0];
  const currentSort = detail.sortOrders.find((sortOrder) => sortOrder.is_current) ?? detail.sortOrders[0];
  const operationIds = new Set(operations.map((operation) => operation.id));

  return (
    <div className="space-y-4">
      <Button onClick={onBack} variant="ghost">
        <span className="inline-flex items-center gap-1">
          <ChevronLeft size={15} />
          Tables
        </span>
      </Button>

      <Panel>
        <div className="flex flex-wrap items-center gap-5">
          <ScoreRing score={table.health_score} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-mono text-2xl text-zinc-950">{table.name}</h2>
              <Badge>{envName}</Badge>
              <Badge>v{table.format_version}</Badge>
            </div>
            <div className="mt-1 truncate font-mono text-sm text-zinc-400">{table.location}</div>
          </div>
          <div className="ml-auto flex flex-wrap gap-2">
            <Button onClick={() => setTab("preview")}>
              <span className="inline-flex items-center gap-2">
                <Eye size={15} />
                Preview
              </span>
            </Button>
            <Button onClick={() => onOpenOperation("rewrite_data_files", table)} variant="primary">
              <span className="inline-flex items-center gap-2">
                <Wrench size={15} />
                Run maintenance
              </span>
            </Button>
          </div>
        </div>
      </Panel>

      <div className="flex gap-6 overflow-x-auto border-b border-zinc-200">
        {DETAIL_TABS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`shrink-0 border-b-2 px-1 pb-2 text-sm ${tab === key ? "border-zinc-950 font-medium text-zinc-950" : "border-transparent text-zinc-500 hover:text-zinc-900"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {detailError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{detailError}</div> : null}

      {tab === "overview" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title="Properties">
            <dl className="space-y-3 text-sm">
              <KeyValue label="Data files" value={table.metrics?.file_count.toLocaleString()} />
              <KeyValue label="Data size" value={formatBytes(table.metrics?.data_size_bytes ?? 0)} />
              <KeyValue label="Delete files" value={table.metrics?.delete_file_count.toLocaleString()} />
              <KeyValue label="Snapshots" value={table.metrics?.snapshot_count.toLocaleString()} />
              <KeyValue label="Small-file ratio" value={table.metrics?.small_file_ratio.toFixed(2)} />
              <KeyValue label="Last compaction" value={relativeDate(table.metrics?.last_compaction_at)} />
              <KeyValue label="Partition spec" value={formatPartitionSpec(currentPartition)} />
              <KeyValue label="Sort order" value={formatSortOrder(currentSort)} />
            </dl>
          </Panel>
          <Panel title="Health score breakdown" right={<Badge tone={toneForScore(health?.score ?? table.health_score)}>{health?.score ?? table.health_score} / 100</Badge>}>
            <div className="space-y-4">
              {(health?.dimensions ?? []).map((dimension) => (
                <div key={dimension.name}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-zinc-600">
                      {dimension.name} <span className="text-zinc-400">- {dimension.weight}%</span>
                    </span>
                    <span className={toneText(toneForScore(dimension.score))}>{dimension.score}</span>
                  </div>
                  <div className="h-1.5 rounded bg-zinc-100">
                    <div className={`h-1.5 rounded ${toneBar(toneForScore(dimension.score))}`} style={{ width: `${dimension.score}%` }} />
                  </div>
                </div>
              ))}
              <p className="text-sm text-zinc-400">Composite, weighted. Any data-loss-risk condition caps the score into the red regardless of other dimensions.</p>
            </div>
          </Panel>
          <div className="lg:col-span-2">
            <Panel title="Findings">
              <div className="grid gap-2 md:grid-cols-2">
                {(health?.findings ?? []).map((finding) => (
                  <div key={finding.message} className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-zinc-800">{finding.message}</span>
                      <Badge tone={finding.severity === "critical" ? "critical" : "warning"}>{finding.severity}</Badge>
                    </div>
                    {finding.operation_ids.length ? (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {finding.operation_ids.map((id) => (
                          <button
                            key={id}
                            onClick={() => onOpenOperation(id, table)}
                            className="rounded-md border border-zinc-300 bg-white px-2 py-1 font-mono text-xs text-zinc-700 hover:bg-zinc-100"
                          >
                            {id}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
                {!health?.findings.length ? <div className="text-sm text-zinc-400">No open findings.</div> : null}
              </div>
            </Panel>
          </div>
        </div>
      ) : null}

      {tab === "schema" ? (
        <Panel title="Schema" right={<Badge tone="warning">drift vs prod: +1 column</Badge>} pad={false}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">#</th>
                  <th className="px-4 py-2 font-medium">Column</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Required</th>
                  <th className="px-4 py-2 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody>
                {schemaFields.map((field, index) => (
                  <tr key={String(field.name ?? index)} className="border-b border-zinc-100 last:border-0">
                    <td className="px-4 py-3 font-mono text-zinc-400">{index + 1}</td>
                    <td className="px-4 py-3 font-mono text-zinc-900">{String(field.name ?? "")}</td>
                    <td className="px-4 py-3 font-mono text-zinc-600">{String(field.type ?? "")}</td>
                    <td className="px-4 py-3 text-zinc-600">{field.required ? "yes" : "no"}</td>
                    <td className="px-4 py-3 text-zinc-500">{String(field.note ?? "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-zinc-200 p-4">
            <Button onClick={() => onOpenOperation("add_column", table)}>Add column</Button>
            <Button onClick={() => onOpenOperation("rename_column", table)}>Rename column</Button>
            <Button onClick={() => onOpenOperation("drop_column", table)} variant="danger">
              Drop column
            </Button>
            <span className="text-xs text-zinc-400">Drop/rename run a consumer-impact check first.</span>
          </div>
        </Panel>
      ) : null}

      {tab === "partitions" ? (
        <div className="space-y-4">
          <Panel title="Current partition spec">
            <dl className="space-y-3 text-sm">
              <KeyValue label="Field" value={formatPartitionSpec(currentPartition)} />
              <KeyValue label="Spec id" value={currentPartition?.spec_id ?? "none"} />
              <KeyValue label="Partition skew" value={<Badge tone="warning">moderate</Badge>} />
              <KeyValue label="Sort order" value={formatSortOrder(currentSort)} />
            </dl>
          </Panel>
          <Panel title="Recommendation">
            <p className="text-sm text-zinc-600">
              Two hot partitions hold 38% of files. Consider a sort-compaction on user_id to restore pruning, then re-evaluate the spec.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button onClick={() => onOpenOperation("rewrite_data_files", table)}>
                <span className="inline-flex items-center gap-2">
                  <Wrench size={15} />
                  Plan sort compaction
                </span>
              </Button>
              <Button onClick={() => onOpenOperation("add_time_partition", table)}>Add partition field</Button>
              <Button onClick={() => onOpenOperation("replace_partition_field", table)}>Change granularity</Button>
            </div>
          </Panel>
        </div>
      ) : null}

      {tab === "snapshots" ? (
        <Panel
          title="Snapshots & time travel"
          right={
            <Button onClick={() => onOpenOperation("create_tag", table)}>
              <span className="inline-flex items-center gap-2">
                <Tag size={15} />
                Create restore point
              </span>
            </Button>
          }
          pad={false}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Snapshot</th>
                  <th className="px-4 py-2 font-medium">Time</th>
                  <th className="px-4 py-2 font-medium">Operation</th>
                  <th className="px-4 py-2 font-medium">Files +/-</th>
                  <th className="px-4 py-2 font-medium">Size</th>
                  <th className="px-4 py-2 font-medium">Ref</th>
                  <th className="px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {detail.snapshots.map((snapshot) => (
                  <tr key={snapshot.id} className="border-b border-zinc-100 last:border-0">
                    <td className="px-4 py-3 font-mono">
                      {snapshot.snapshot_id}
                      {snapshot.snapshot_id === table.current_snapshot_id ? <div className="mt-1"><Badge tone="healthy">current</Badge></div> : null}
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-600">{formatDateTime(snapshot.committed_at)}</td>
                    <td className="px-4 py-3">
                      <Badge>{snapshot.operation}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-600">
                      +{numberFromSummary(snapshot.summary, "added_files")} / -{numberFromSummary(snapshot.summary, "removed_files")}
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-600">{signedBytes(numberFromSummary(snapshot.summary, "bytes"))}</td>
                    <td className="px-4 py-3">{refsForSnapshot(detail.refs, snapshot.snapshot_id)}</td>
                    <td className="px-4 py-3 text-right">
                      {snapshot.snapshot_id !== table.current_snapshot_id ? (
                        <button
                          onClick={() => onOpenOperation("rollback_to_snapshot", table)}
                          className="inline-flex items-center gap-2 rounded-md px-2 py-1 text-zinc-600 hover:bg-zinc-100"
                        >
                          <RotateCcw size={15} />
                          Roll back
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : null}

      {tab === "refs" ? (
        <div className="space-y-4">
          <Panel title="Refs" pad={false}>
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Kind</th>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Snapshot</th>
                  <th className="px-4 py-2 font-medium">Retention</th>
                </tr>
              </thead>
              <tbody>
                {detail.refs.map((ref) => (
                  <tr key={ref.id} className="border-b border-zinc-100 last:border-0">
                    <td className="px-4 py-3">
                      <Badge>{ref.ref_type === "branch" ? <GitBranch size={12} /> : <Tag size={12} />} {ref.ref_type}</Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-900">{ref.name}</td>
                    <td className="px-4 py-3 font-mono text-zinc-500">{ref.snapshot_id}</td>
                    <td className="px-4 py-3 font-mono text-zinc-600">{retentionLabel(ref.retention)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <Panel title="Write-audit-publish">
            <p className="text-sm text-zinc-600">Stage writes on an audit branch, validate, then fast-forward main.</p>
            <div className="mt-4 grid gap-2">
              <Button onClick={() => onOpenOperation("create_branch", table)} full>
                <span className="inline-flex items-center gap-2">
                  <GitBranch size={15} />
                  Create audit branch
                </span>
              </Button>
              <Button onClick={() => onOpenOperation("fast_forward", table)} variant="primary" full>
                Publish to main
              </Button>
            </div>
          </Panel>
        </div>
      ) : null}

      {tab === "maintenance" ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {MAINTENANCE_CARDS.map((card) => (
            <Panel key={`${card.id}-${card.title}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-zinc-900">{card.title}</div>
                  <div className="mt-1 text-sm text-zinc-500">{card.body}</div>
                </div>
                {card.recommended ? <Badge tone="warning">recommended</Badge> : card.gated ? <Lock size={16} className="text-zinc-400" /> : null}
              </div>
              <Button onClick={() => onOpenOperation(card.id, table)} full disabled={!operationIds.has(card.id)}>
                <span className="inline-flex items-center gap-2">
                  <Play size={15} />
                  Dry run
                </span>
              </Button>
            </Panel>
          ))}
        </div>
      ) : null}

      {tab === "preview" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {PREVIEW_RESOURCES.map((resource) => (
              <button
                key={resource}
                onClick={() => setPreviewResource(resource)}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 font-mono text-sm ${previewResource === resource ? "border-zinc-900 bg-zinc-900 text-white" : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50"}`}
              >
                <Table2 size={15} />
                {resource}
              </button>
            ))}
            <div className="ml-auto text-xs text-zinc-400">read-only - rate-limited - sensitive columns masked</div>
          </div>
          {previewError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{previewError}</div> : null}
          <Panel title={<span className="font-mono">{preview?.query ?? "SELECT ..."}</span>} pad={false}>
            <PreviewTable preview={preview} />
          </Panel>
        </div>
      ) : null}

      {tab === "settings" ? (
        <Panel title="Table properties" pad={false}>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries({
                "write.target-file-size-bytes": 536870912,
                "write.format.default": table.properties["write.format.default"] ?? "parquet",
                "history.expire.max-snapshot-age-ms": 604800000,
                "commit.retry.num-retries": 4,
                owner: table.owner ?? "unassigned",
                "sla.freshness": "15m",
                ...table.properties
              }).map(([key, value]) => (
                <tr key={key} className="border-b border-zinc-100 last:border-0">
                  <td className="px-4 py-3 font-mono text-zinc-500">{key}</td>
                  <td className="px-4 py-3 font-mono text-zinc-900">{displayValue(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex flex-wrap gap-2 border-t border-zinc-200 p-4">
            <Button onClick={() => onOpenOperation("set_tblproperties", table)}>
              <span className="inline-flex items-center gap-2">
                <Settings size={15} />
                Set property
              </span>
            </Button>
            <Button onClick={() => onOpenOperation("unset_tblproperties", table)}>Unset property</Button>
            <Button onClick={() => onOpenOperation("upgrade_format", table)} variant="danger">
              Upgrade format
            </Button>
          </div>
        </Panel>
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
    <div className="flex rounded-md border border-zinc-300 bg-white p-0.5 text-sm">
      {items.map(([key, label]) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`rounded px-3 py-1 ${value === key ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function ScoreRing({ score }: { score: number }) {
  const tone = toneForScore(score);
  const color = tone === "healthy" ? "#059669" : tone === "warning" ? "#d97706" : "#dc2626";
  return (
    <div
      className="grid h-20 w-20 shrink-0 place-items-center rounded-full"
      style={{ background: `conic-gradient(${color} ${score * 3.6}deg, #f4f4f5 0deg)` }}
    >
      <div className="grid h-14 w-14 place-items-center rounded-full bg-white font-semibold" style={{ color }}>
        {score}
      </div>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="font-mono text-zinc-900">{value ?? "unknown"}</dd>
    </div>
  );
}

function PreviewTable({ preview }: { preview: TablePreviewRead | null }) {
  if (!preview) {
    return <div className="p-8 text-center text-sm text-zinc-400">Loading preview...</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm">
        <thead className="border-b border-zinc-200 text-left text-xs text-zinc-500">
          <tr>
            {preview.columns.map((column) => (
              <th key={column} className="px-4 py-2 font-mono font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.rows.map((row, index) => (
            <tr key={index} className="border-b border-zinc-100 last:border-0">
              {preview.columns.map((column) => (
                <td key={column} className="max-w-[420px] truncate px-4 py-2.5 font-mono text-zinc-700">
                  {displayValue(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function namespaceOf(name: string) {
  return name.includes(".") ? name.split(".")[0] : "default";
}

function relativeDate(value: string | null | undefined) {
  if (!value) return "never";
  const timestamp = new Date(value).getTime();
  const deltaMs = Date.now() - timestamp;
  const hours = Math.max(1, Math.round(deltaMs / 3_600_000));
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().slice(0, 16).replace("T", " ");
}

function asRecords(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null) : [];
}

function formatPartitionSpec(spec: PartitionSpecRead | undefined) {
  const fields = asRecords(spec?.spec.fields);
  if (!fields.length) return "unpartitioned";
  return fields
    .map((field) => {
      const transform = String(field.transform ?? "identity");
      const source = String(field.source ?? field.column ?? "");
      return transform === "identity" ? source : `${transform}(${source})`;
    })
    .join(", ");
}

function formatSortOrder(sortOrder: SortOrderRead | undefined) {
  const fields = asRecords(sortOrder?.fields);
  if (!fields.length) return "unsorted";
  return fields.map((field) => `${String(field.source ?? "")} ${String(field.direction ?? "asc").toUpperCase()}`).join(", ");
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function numberFromSummary(summary: Record<string, unknown>, key: string) {
  const value = summary[key];
  return typeof value === "number" ? value : Number(value ?? 0);
}

function signedBytes(bytes: number) {
  const sign = bytes > 0 ? "+" : bytes < 0 ? "-" : "";
  return `${sign} ${formatBytes(Math.abs(bytes))}`;
}

function refsForSnapshot(refs: TableRefRead[], snapshotId: string) {
  const matches = refs.filter((ref) => ref.snapshot_id === snapshotId);
  if (!matches.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {matches.map((ref) => (
        <Badge key={ref.id}>{ref.name}</Badge>
      ))}
    </div>
  );
}

function retentionLabel(retention: Record<string, unknown>) {
  if (retention.pinned) return "pinned";
  if (retention.retain) return String(retention.retain);
  if (retention.max_ref_age) return `max-ref-age ${String(retention.max_ref_age)}`;
  if (retention.type) return String(retention.type);
  return "default";
}

function toneText(tone: "healthy" | "warning" | "critical") {
  return tone === "healthy" ? "text-emerald-700" : tone === "warning" ? "text-amber-700" : "text-red-700";
}

function toneBar(tone: "healthy" | "warning" | "critical") {
  return tone === "healthy" ? "bg-emerald-600" : tone === "warning" ? "bg-amber-600" : "bg-red-600";
}
