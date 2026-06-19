"use client";

import { ChevronDown, Database, HardDrive, Lock, Pencil, Plus, RefreshCw, Server, Trash2, X } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import type { ControlContext } from "@/app/page";
import { api } from "@/lib/api";
import type {
  CatalogConnectionRead,
  ComputeBackendRead,
  ConnectionTestResult,
  EnvironmentRead,
  ObjectStoreConnectionRead,
  TableIndexRefreshResult,
  TableRead
} from "@/types/api";

const CATALOGS = [
  ["rest", "REST", "Polaris - Unity - Lakekeeper - generic"],
  ["jdbc", "JDBC", "PostgreSQL - MySQL"],
  ["hive", "Hive Metastore", "Thrift"],
  ["glue", "AWS Glue", "IAM / Lake Formation"],
  ["nessie", "Nessie", "Git-style branches"],
  ["s3_tables", "S3 Tables", "AWS managed"],
  ["hadoop", "Hadoop", "filesystem - dev only"]
] as const;

const STORES = [
  ["s3", "S3 / compatible"],
  ["gcs", "GCS"],
  ["adls", "Azure ADLS"],
  ["hdfs", "HDFS"],
  ["local", "Local"]
] as const;

const CATALOG_AUTHS = [
  ["none", "None / URI", "Embedded URI credentials or open dev catalog"],
  ["basic", "Username + password", "JDBC, Hive, or basic REST auth"],
  ["bearer", "Bearer token", "REST catalog token"],
  ["oauth_client", "OAuth client", "client credentials flow"],
  ["aws_iam", "AWS IAM", "Glue, S3 Tables, Lake Formation"],
  ["secret_ref", "Secret reference", "Vault - Secrets Manager - Key Vault"]
] as const;

const STORAGE_AUTHS = [
  ["credential_vending", "Catalog-vended", "REST/S3 Tables returns scoped storage credentials"],
  ["keyless", "Keyless identity", "IAM role - IRSA - Workload Identity"],
  ["static_key", "AWS access key", "access key id + secret access key"],
  ["secret_ref", "Secret reference", "Vault - Secrets Manager - Key Vault"]
] as const;

const CAPABILITY_PREVIEW: Record<string, { good: string[]; bad: string[]; note: string }> = {
  rest: {
    good: ["credential vending", "multi-table commit", "branch / tag", "scan planning"],
    bad: [],
    note: "REST catalogs can vend credentials and centralize commit coordination when the server supports it."
  },
  jdbc: {
    good: ["metadata read / write", "DML / DDL", "branch / tag ops", "controlled dry-runs"],
    bad: ["credential vending", "server-side commit deconflicting", "multi-table commits"],
    note: "JDBC catalogs commit through the metadata DB directly. Data rewrite execution still needs an enabled runtime."
  },
  hive: {
    good: ["read / write", "schema evolution"],
    bad: ["credential vending", "REST scan planning"],
    note: "Hive Metastore catalogs work, but capability probing keeps REST-only features disabled."
  },
  glue: {
    good: ["read / write", "Lake Formation integration"],
    bad: ["v3 create through REST", "credential vending"],
    note: "Glue support depends on account-level permissions and table format settings."
  },
  nessie: {
    good: ["catalog-level branching", "global time travel"],
    bad: ["credential vending"],
    note: "Nessie exposes catalog-wide references and branch workflows."
  },
  s3_tables: {
    good: ["managed maintenance", "v3", "credential vending"],
    bad: [],
    note: "S3 Tables manages catalog and table maintenance in the provider service."
  },
  hadoop: {
    good: ["filesystem pointers"],
    bad: ["production coordination"],
    note: "Hadoop catalogs are useful for local and dev workflows only."
  }
};

type CatalogType = (typeof CATALOGS)[number][0];
type StoreType = (typeof STORES)[number][0];
type CatalogAuthType = (typeof CATALOG_AUTHS)[number][0];
type StorageAuthType = (typeof STORAGE_AUTHS)[number][0];
type JdbcSslMode = "disable" | "allow" | "prefer" | "require" | "verify-ca" | "verify-full";

type FormState = {
  envName: string;
  name: string;
  catalog: CatalogType;
  uri: string;
  warehouse: string;
  store: StoreType;
  region: string;
  endpoint: string;
  accessStyle: "virtual-hosted" | "path-style";
  sse: "none" | "s3" | "kms" | "dsse-kms";
  kmsKeyArn: string;
  remoteSigning: boolean;
  catalogAuth: CatalogAuthType;
  catalogUsername: string;
  catalogPassword: string;
  catalogBearerToken: string;
  catalogClientId: string;
  catalogClientSecret: string;
  catalogIdentity: string;
  catalogSecretReference: string;
  jdbcSslMode: JdbcSslMode;
  jdbcSslRootCert: string;
  jdbcApplicationName: string;
  storageAuth: StorageAuthType;
  storageIdentity: string;
  storageSecretReference: string;
  awsAccessKeyId: string;
  awsSecretAccessKey: string;
  awsSessionToken: string;
};

const DEFAULT_FORM: FormState = {
  envName: "",
  name: "",
  catalog: "rest",
  uri: "",
  warehouse: "",
  store: "s3",
  region: "",
  endpoint: "",
  accessStyle: "virtual-hosted",
  sse: "none",
  kmsKeyArn: "",
  remoteSigning: false,
  catalogAuth: "none",
  catalogUsername: "",
  catalogPassword: "",
  catalogBearerToken: "",
  catalogClientId: "",
  catalogClientSecret: "",
  catalogIdentity: "",
  catalogSecretReference: "",
  jdbcSslMode: "prefer",
  jdbcSslRootCert: "",
  jdbcApplicationName: "iceyard",
  storageAuth: "keyless",
  storageIdentity: "",
  storageSecretReference: "",
  awsAccessKeyId: "",
  awsSecretAccessKey: "",
  awsSessionToken: ""
};

export function Connections({
  token,
  environments,
  connections,
  objectStores,
  computeBackends,
  tables,
  context,
  onRefresh
}: {
  token: string;
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
  objectStores: ObjectStoreConnectionRead[];
  computeBackends: ComputeBackendRead[];
  tables: TableRead[];
  context: ControlContext;
  onRefresh: () => Promise<void>;
}) {
  const [showWizard, setShowWizard] = useState(false);
  const [editingConnection, setEditingConnection] = useState<CatalogConnectionRead | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [testingIds, setTestingIds] = useState<Set<string>>(() => new Set());
  const [syncingIds, setSyncingIds] = useState<Set<string>>(() => new Set());
  const [openSyncMenuId, setOpenSyncMenuId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ConnectionTestResult>>({});
  const [syncResults, setSyncResults] = useState<Record<string, TableIndexRefreshResult>>({});
  const tablesByEnvironment = useMemo(() => {
    const counts = new Map<string, number>();
    for (const table of tables) counts.set(table.environment_id, (counts.get(table.environment_id) ?? 0) + 1);
    return counts;
  }, [tables]);

  async function deleteConnection(connection: CatalogConnectionRead) {
    if (!window.confirm(`Delete catalog connection "${connection.name}"? Synced metadata for tables using it will be removed from Iceyard.`)) {
      return;
    }
    setActionError(null);
    try {
      await api.deleteCatalogConnection(token, connection.id);
      await onRefresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to delete connection.");
    }
  }

  async function deleteObjectStore(store: ObjectStoreConnectionRead) {
    if (!window.confirm(`Delete storage connection "${store.name}"? Catalog connections linked to it should be updated first.`)) {
      return;
    }
    setActionError(null);
    try {
      await api.deleteObjectStoreConnection(token, store.id);
      await onRefresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to delete storage connection.");
    }
  }

  async function testCatalog(connection: CatalogConnectionRead) {
    setActionError(null);
    setTestingIds((current) => new Set(current).add(connection.id));
    try {
      const result = await api.testCatalogConnection(token, connection.id);
      setTestResults((current) => ({ ...current, [connection.id]: result }));
      await onRefresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to test connection.");
    } finally {
      setTestingIds((current) => {
        const next = new Set(current);
        next.delete(connection.id);
        return next;
      });
    }
  }

  async function syncCatalog(connection: CatalogConnectionRead, force = false) {
    setActionError(null);
    setSyncingIds((current) => new Set(current).add(connection.id));
    try {
      const result = await api.syncCatalogMetadata(token, connection.id, { force });
      setSyncResults((current) => ({ ...current, [connection.id]: result }));
      await onRefresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to sync metadata.");
    } finally {
      setSyncingIds((current) => {
        const next = new Set(current);
        next.delete(connection.id);
        return next;
      });
    }
  }

  async function testObjectStore(store: ObjectStoreConnectionRead) {
    setActionError(null);
    setTestingIds((current) => new Set(current).add(store.id));
    try {
      const result = await api.testObjectStoreConnection(token, store.id);
      setTestResults((current) => ({ ...current, [store.id]: result }));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Unable to test storage connection.");
    } finally {
      setTestingIds((current) => {
        const next = new Set(current);
        next.delete(store.id);
        return next;
      });
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-500">
          The catalog and Iceberg metadata files remain the source of truth. Iceyard stores a rebuildable metadata cache for search, previews, and audit.
        </p>
        <Button variant="primary" onClick={() => setShowWizard(true)}>
          <span className="inline-flex items-center gap-2">
            <Plus size={15} />
            Add connection
          </span>
        </Button>
      </div>

      {actionError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{actionError}</div> : null}

      <div className="space-y-4">
        {environments.map((environment) => {
          const envConnections = connections.filter((connection) => connection.environment_id === environment.id);
          const envStores = objectStores.filter((store) => store.environment_id === environment.id);
          const envBackends = computeBackends.filter((backend) => backend.environment_id === environment.id && backend.is_enabled);
          return (
            <Panel
              key={environment.id}
              title={
                <span className="flex items-center gap-2">
                  {environment.name}
                  {environment.kind !== environment.name ? <Badge>{environment.kind}</Badge> : null}
                </span>
              }
              right={<span className="text-xs text-zinc-400">{tablesByEnvironment.get(environment.id) ?? 0} synced tables</span>}
            >
              <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
                <div className="space-y-3">
                  {envConnections.map((connection) => (
                    <div key={connection.id} className="rounded-md border border-zinc-200 p-3">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="truncate font-medium text-zinc-900">{connection.name}</span>
                          <span className="text-xs text-zinc-400">
                            {connection.catalog_type} · {connection.is_enabled ? "connected" : "disabled"}
                          </span>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className="text-xs text-zinc-400">
                            {connection.last_tested_at ? `tested ${new Date(connection.last_tested_at).toLocaleTimeString()}` : "not tested"}
                          </span>
                          <ConnectionSyncMenu
                            open={openSyncMenuId === connection.id}
                            onOpenChange={(open) => setOpenSyncMenuId(open ? connection.id : null)}
                            testing={testingIds.has(connection.id)}
                            syncing={syncingIds.has(connection.id)}
                            disabled={!connection.is_enabled}
                            result={syncResults[connection.id]}
                            onTest={() => void testCatalog(connection)}
                            onSync={() => void syncCatalog(connection)}
                            onForceSync={() => void syncCatalog(connection, true)}
                          />
                          <Button onClick={() => setEditingConnection(connection)}>
                            <Pencil size={14} /> Edit
                          </Button>
                          <Button variant="danger" onClick={() => void deleteConnection(connection)}>
                            <Trash2 size={14} /> Delete
                          </Button>
                        </div>
                      </div>
                      <dl className="space-y-3 text-sm">
                        <ConnectionRow icon={<Database size={15} />} label="Catalog" value={`${connection.catalog_type.toUpperCase()} - ${connection.settings.provider ?? "configured"}`} />
                        <ConnectionRow icon={<Server size={15} />} label="Catalog URI" value={connection.endpoint ?? "not set"} mono />
                        <ConnectionRow icon={<HardDrive size={15} />} label="Object storage" value={connection.warehouse ?? "not set"} mono />
                        <ConnectionRow label="Region" value={environment.region ?? String(connection.settings.region ?? "not set")} />
                        <ConnectionRow label="Synced tables" value={tables.filter((table) => table.catalog_connection_id === connection.id).length} />
                      </dl>
                      <div className="mt-4 border-t border-zinc-100 pt-4">
                        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">Capabilities probed</div>
                        <div className="flex flex-wrap gap-1.5">
                          {capabilityLabels(connection.capabilities).good.map((capability) => (
                            <Badge key={capability} tone="healthy">
                              {capability}
                            </Badge>
                          ))}
                          {capabilityLabels(connection.capabilities).bad.map((capability) => (
                            <span key={capability} className="rounded-md border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 text-xs text-zinc-400 line-through">
                              {capability}
                            </span>
                          ))}
                        </div>
                      </div>
                      <p className="mt-3 text-xs text-zinc-400">{CAPABILITY_PREVIEW[connection.catalog_type]?.note ?? "Capabilities are driven by the connection probe."}</p>
                      {testResults[connection.id] ? <ConnectionTestSummary result={testResults[connection.id]} /> : null}
                    </div>
                  ))}
                  {!envConnections.length ? <div className="rounded-md border border-zinc-200 p-4 text-sm text-zinc-400">No catalog connections in this environment.</div> : null}
                  {envStores.length ? (
                    <div className="rounded-md border border-zinc-200 p-3">
                      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-400">Manifest & table storage</div>
                      <div className="space-y-2">
                        {envStores.map((store) => (
                          <div key={store.id} className="flex items-center justify-between gap-3 rounded-md bg-zinc-50 px-3 py-2 text-sm">
                            <div className="min-w-0">
                              <div className="font-medium text-zinc-900">{store.name}</div>
                              <div className="truncate font-mono text-xs text-zinc-500">
                                {store.store_type} · {String(store.settings.warehouse ?? store.endpoint ?? "no warehouse")}
                              </div>
                              {testResults[store.id] ? <ConnectionTestSummary result={testResults[store.id]} compact /> : null}
                            </div>
                            <div className="flex shrink-0 gap-2">
                              <Button onClick={() => void testObjectStore(store)} disabled={testingIds.has(store.id)}>
                                {testingIds.has(store.id) ? "Testing..." : "Test"}
                              </Button>
                              <Button variant="danger" onClick={() => void deleteObjectStore(store)}>
                                <Trash2 size={14} /> Delete
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
                <RuntimePanel environment={environment} connections={envConnections} computeBackends={envBackends} />
              </div>
            </Panel>
          );
        })}
      </div>

      {showWizard ? (
        <AddConnectionWizard
          token={token}
          environments={environments}
          onClose={() => setShowWizard(false)}
          onRefresh={onRefresh}
        />
      ) : null}
      {editingConnection ? (
        <AddConnectionWizard
          token={token}
          environments={environments}
          initialConnection={editingConnection}
          initialObjectStore={linkedStoreForConnection(editingConnection, objectStores)}
          onClose={() => setEditingConnection(null)}
          onRefresh={onRefresh}
        />
      ) : null}
    </div>
  );
}

function RuntimePanel({
  environment,
  connections,
  computeBackends
}: {
  environment: EnvironmentRead;
  connections: CatalogConnectionRead[];
  computeBackends: ComputeBackendRead[];
}) {
  const hasWritableCatalog = connections.some((connection) => connection.is_enabled && connection.capabilities.can_update_table_via_protocol !== false);
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <div className="mb-3 text-sm font-medium text-zinc-900">Runtime & execution</div>
      <div className="space-y-2 text-sm">
        <RuntimeRow
          label="Native catalog operations"
          value={hasWritableCatalog ? "enabled" : "unavailable"}
          tone={hasWritableCatalog ? "healthy" : "neutral"}
          detail={hasWritableCatalog ? "Metadata and catalog-scoped work use the selected catalog connection." : "No enabled catalog can update table metadata."}
        />
        <RuntimeRow
          label="Internal worker"
          value="enabled"
          tone="healthy"
          detail="Dry-runs, gate checks, approvals, audit, and metadata-safe queueing run inside the API service."
        />
        <RuntimeRow
          label="Compute backend"
          value={computeBackends.length ? computeBackends.map((backend) => backend.name).join(", ") : "not configured"}
          tone={computeBackends.length ? "healthy" : "warning"}
          detail={
            computeBackends.length
              ? `Heavy rewrites can target configured ${environment.name} compute backends when an adapter is enabled.`
              : "Heavy data rewrites remain dry-run/approval-only until Spark, Trino, Flink, or a native backend is connected."
          }
        />
      </div>
    </div>
  );
}

function RuntimeRow({
  label,
  value,
  detail,
  tone
}: {
  label: string;
  value: string;
  detail: string;
  tone: "neutral" | "healthy" | "warning" | "critical";
}) {
  return (
    <div className="rounded-md border border-zinc-200 bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium text-zinc-800">{label}</span>
        <Badge tone={tone}>{value}</Badge>
      </div>
      <p className="mt-1 text-xs text-zinc-500">{detail}</p>
    </div>
  );
}

function AddConnectionWizard({
  token,
  environments,
  initialConnection,
  initialObjectStore,
  onClose,
  onRefresh
}: {
  token: string;
  environments: EnvironmentRead[];
  initialConnection?: CatalogConnectionRead;
  initialObjectStore?: ObjectStoreConnectionRead | null;
  onClose: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [form, setForm] = useState<FormState>(() => ({
    ...formFromConnection(initialConnection, initialObjectStore, environments)
  }));
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const caps = CAPABILITY_PREVIEW[form.catalog];
  const isEditing = Boolean(initialConnection);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function saveConnection() {
    setError(null);
    setMessage(null);
    setTestResult(null);
    if (!form.envName || !form.name || !form.uri || !form.warehouse) {
      setError("Environment, connection name, catalog URI, and warehouse are required.");
      return;
    }
    const validationError = credentialValidationError(form, isEditing);
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    try {
      let environment = environments.find((item) => item.name === form.envName);
      if (!environment) {
        environment = await api.createEnvironment(token, {
          name: form.envName,
          kind: form.envName,
          region: form.region,
          posture: {
            approval_required: form.envName === "prod",
            protected_branches: ["main"]
          }
        });
      }
      const objectStorePayload = {
        environment_id: environment.id,
        name: `${form.name}-storage`,
        store_type: form.store,
        endpoint: form.endpoint || undefined,
        region: form.region,
        auth_ref: storageAuthRefForSave(form, initialObjectStore),
        settings: {
          warehouse: form.warehouse,
          access_style: form.accessStyle,
          server_side_encryption: form.sse,
          kms_key_arn: form.kmsKeyArn,
          credential_vending: form.storageAuth === "credential_vending",
          remote_signing: form.remoteSigning,
          storage_auth: storageAuthSettings(form)
        }
      };
      const objectStore =
        isEditing && initialObjectStore
          ? await api.updateObjectStoreConnection(token, initialObjectStore.id, objectStorePayload)
          : await api.createObjectStoreConnection(token, objectStorePayload);
      const catalogPayload = {
        environment_id: environment.id,
        name: form.name,
        catalog_type: form.catalog,
        endpoint: form.uri,
        warehouse: form.warehouse,
        auth_ref: catalogAuthRefForSave(form, initialConnection),
        settings: {
          storage: form.store,
          region: form.region,
          endpoint: form.endpoint,
          access_style: form.accessStyle,
          server_side_encryption: form.sse,
          kms_key_arn: form.kmsKeyArn,
          credential_vending: form.storageAuth === "credential_vending",
          remote_signing: form.remoteSigning,
          jdbc_options: jdbcOptions(form),
          catalog_auth: catalogAuthSettings(form),
          object_store_connection_id: objectStore.id
        }
      };
      const catalogConnection =
        isEditing && initialConnection
          ? await api.updateCatalogConnection(token, initialConnection.id, catalogPayload)
          : await api.createCatalogConnection(token, catalogPayload);
      const result = await api.testCatalogConnection(token, catalogConnection.id);
      setTestResult(result);
      if (result.status === "failed") {
        setError("Connection saved, but the test failed. Review the component results below.");
      } else {
        setMessage(result.message);
      }
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save connection.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 p-4" onClick={onClose}>
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-lg border border-zinc-200 bg-white shadow-xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3">
          <div>
            <div className="text-sm font-medium text-zinc-900">
              {isEditing ? "Edit lakehouse connection" : "Add lakehouse connection"}
            </div>
            <div className="mt-0.5 text-xs text-zinc-400">
              {isEditing
                ? "Update catalog metadata, storage settings, and credentials. Stored secrets are never displayed."
                : "Create the environment, catalog metadata connection, and manifest/table storage reference used by Iceyard."}
            </div>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-zinc-400 hover:bg-zinc-100">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-6 overflow-auto p-5">
          <div className="grid gap-3 md:grid-cols-3">
            <SetupStep
              title="1. Environment"
              body="A deployment boundary such as dev, staging, or prod. Policies and approvals key off this scope."
            />
            <SetupStep
              title="2. Catalog metadata"
              body="REST, JDBC, Glue, Hive, Nessie, S3 Tables, or Hadoop. JDBC points at the catalog database."
            />
            <SetupStep
              title="3. Manifest storage"
              body="Object storage or filesystem location where table metadata, manifests, and data files live."
            />
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Field label="connection name" value={form.name} onChange={(value) => set("name", value)} placeholder="catalog name" />
            <Field
              label="environment"
              value={form.envName}
              onChange={(value) => set("envName", value)}
              placeholder={environments.length ? environments.map((environment) => environment.name).join(", ") : "environment name"}
              hint="Existing names are reused; new names are created."
            />
            <Field label="region" value={form.region} onChange={(value) => set("region", value)} placeholder="eu-central-1" />
          </div>

          <section className="space-y-3">
            <div>
              <Eyebrow>Catalog metadata / database</Eyebrow>
              <p className="mt-1 text-sm text-zinc-500">
                This is the control-plane entrypoint for namespaces, table metadata, commits, snapshots, branches, and tags.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {CATALOGS.map(([value, label, sub]) => (
                <Choice key={value} active={form.catalog === value} label={label} sub={sub} onClick={() => set("catalog", value)} />
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Field label={catalogUriLabel(form.catalog)} value={form.uri} onChange={(value) => set("uri", value)} placeholder="catalog endpoint or JDBC URI" />
              <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-600">
                {catalogHelp(form.catalog)}
              </div>
            </div>
            {form.catalog === "jdbc" ? (
              <div className="space-y-3 rounded-md border border-zinc-200 p-3">
                <div>
                  <div className="text-sm font-medium text-zinc-900">JDBC TLS</div>
                  <p className="mt-1 text-xs text-zinc-500">
                    PostgreSQL catalogs often require SSL in pg_hba.conf. Use require to force TLS, or verify-ca/verify-full with a root CA certificate.
                  </p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <Segmented
                    label="sslmode"
                    value={form.jdbcSslMode}
                    items={[
                      ["prefer", "prefer"],
                      ["require", "require"],
                      ["verify-ca", "verify-ca"],
                      ["verify-full", "verify-full"],
                      ["disable", "disable"]
                    ]}
                    onChange={(value) => set("jdbcSslMode", value as JdbcSslMode)}
                  />
                  <Field
                    label="application name"
                    value={form.jdbcApplicationName}
                    onChange={(value) => set("jdbcApplicationName", value)}
                    placeholder="iceyard"
                  />
                </div>
                {form.jdbcSslMode === "verify-ca" || form.jdbcSslMode === "verify-full" ? (
                  <TextArea
                    label="root CA certificate PEM"
                    value={form.jdbcSslRootCert}
                    onChange={(value) => set("jdbcSslRootCert", value)}
                    placeholder="-----BEGIN CERTIFICATE-----"
                  />
                ) : null}
              </div>
            ) : null}
            <div className="space-y-3 rounded-md border border-zinc-200 p-3">
              <div>
                <div className="text-sm font-medium text-zinc-900">Catalog authentication</div>
                <p className="mt-1 text-xs text-zinc-500">
                  Used for the REST/Hive/Glue/Nessie/S3 Tables endpoint or the JDBC metadata database. Storage credentials are configured separately.
                </p>
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                {CATALOG_AUTHS.map(([value, label, sub]) => (
                  <Choice key={value} active={form.catalogAuth === value} label={label} sub={sub} onClick={() => set("catalogAuth", value)} />
                ))}
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {form.catalogAuth === "basic" ? (
                  <>
                    <Field label="username" value={form.catalogUsername} onChange={(value) => set("catalogUsername", value)} />
                    <PasswordField
                      label="password"
                      value={form.catalogPassword}
                      onChange={(value) => set("catalogPassword", value)}
                      placeholder={isEditing ? "leave blank to keep current password" : undefined}
                    />
                  </>
                ) : null}
                {form.catalogAuth === "bearer" ? (
                  <PasswordField
                    label="bearer token"
                    value={form.catalogBearerToken}
                    onChange={(value) => set("catalogBearerToken", value)}
                    placeholder={isEditing ? "leave blank to keep current token" : undefined}
                  />
                ) : null}
                {form.catalogAuth === "oauth_client" ? (
                  <>
                    <Field label="client id" value={form.catalogClientId} onChange={(value) => set("catalogClientId", value)} />
                    <PasswordField
                      label="client secret"
                      value={form.catalogClientSecret}
                      onChange={(value) => set("catalogClientSecret", value)}
                      placeholder={isEditing ? "leave blank to keep current client secret" : undefined}
                    />
                  </>
                ) : null}
                {form.catalogAuth === "aws_iam" ? (
                  <Field label="role ARN / identity" value={form.catalogIdentity} onChange={(value) => set("catalogIdentity", value)} placeholder="optional if using runtime identity" />
                ) : null}
                {form.catalogAuth === "secret_ref" ? (
                  <Field label="secret reference" value={form.catalogSecretReference} onChange={(value) => set("catalogSecretReference", value)} placeholder="vault/path, secret ARN, or key vault id" />
                ) : null}
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <div>
              <Eyebrow>Manifest & table storage</Eyebrow>
              <p className="mt-1 text-sm text-zinc-500">
                This is the warehouse root or table bucket where Iceberg metadata JSON, manifests, delete files, and data files are stored.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {STORES.map(([value, label]) => (
                <Choice key={value} active={form.store === value} label={label} onClick={() => set("store", value)} compact />
              ))}
            </div>
            <Field label="warehouse / table bucket" value={form.warehouse} onChange={(value) => set("warehouse", value)} placeholder="warehouse URI" />
            {form.store === "s3" ? (
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="endpoint (S3-compatible)" value={form.endpoint} onChange={(value) => set("endpoint", value)} placeholder="https://... (blank = AWS)" />
                <Segmented
                  label="access style"
                  value={form.accessStyle}
                  items={[
                    ["virtual-hosted", "virtual-hosted"],
                    ["path-style", "path-style"]
                  ]}
                  onChange={(value) => set("accessStyle", value as FormState["accessStyle"])}
                />
                <Segmented
                  label="server-side encryption"
                  value={form.sse}
                  items={[
                    ["none", "none"],
                    ["s3", "S3"],
                    ["kms", "kms"],
                    ["dsse-kms", "dsse-kms"]
                  ]}
                  onChange={(value) => set("sse", value as FormState["sse"])}
                />
                <Field label="kms key ARN" value={form.kmsKeyArn} onChange={(value) => set("kmsKeyArn", value)} />
                <label className="flex items-center gap-2 text-sm text-zinc-600">
                  <input type="checkbox" checked={form.remoteSigning} onChange={(event) => set("remoteSigning", event.target.checked)} />
                  Enable remote request signing
                </label>
              </div>
            ) : null}
            <div className="space-y-3 rounded-md border border-zinc-200 p-3">
              <div>
                <div className="text-sm font-medium text-zinc-900">Storage authentication</div>
                <p className="mt-1 text-xs text-zinc-500">
                  Used by the manifest and data-file storage client. Static secrets are accepted once, moved to secret references, and never returned by the API.
                </p>
              </div>
              <div className="grid gap-2 md:grid-cols-4">
                {STORAGE_AUTHS.map(([value, label, sub]) => (
                  <Choice key={value} active={form.storageAuth === value} label={label} sub={sub} onClick={() => set("storageAuth", value)} />
                ))}
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {form.storageAuth === "keyless" ? (
                  <Field label="role ARN / identity" value={form.storageIdentity} onChange={(value) => set("storageIdentity", value)} placeholder="optional if using runtime identity" />
                ) : null}
                {form.storageAuth === "secret_ref" ? (
                  <Field label="secret reference" value={form.storageSecretReference} onChange={(value) => set("storageSecretReference", value)} placeholder="vault/path, secret ARN, or key vault id" />
                ) : null}
                {form.storageAuth === "static_key" ? (
                  <>
                    <Field label="AWS access key id" value={form.awsAccessKeyId} onChange={(value) => set("awsAccessKeyId", value)} />
                    <PasswordField
                      label="AWS secret access key"
                      value={form.awsSecretAccessKey}
                      onChange={(value) => set("awsSecretAccessKey", value)}
                      placeholder={isEditing ? "leave blank to keep current secret key" : undefined}
                    />
                    <PasswordField label="AWS session token (optional)" value={form.awsSessionToken} onChange={(value) => set("awsSessionToken", value)} />
                  </>
                ) : null}
              </div>
              <div className="flex items-start gap-2 rounded-md bg-zinc-50 p-3 text-xs text-zinc-500">
                <Lock size={14} className="mt-0.5 shrink-0" />
                {storageAuthNote(form.storageAuth)}
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <Eyebrow>Probed capabilities (preview)</Eyebrow>
            <div className="flex flex-wrap gap-1.5">
              {caps.good.map((capability) => (
                <Badge key={capability} tone="healthy">
                  {capability}
                </Badge>
              ))}
              {caps.bad.map((capability) => (
                <span key={capability} className="rounded-md border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 text-xs text-zinc-400 line-through">
                  {capability}
                </span>
              ))}
            </div>
            <p className="text-sm text-zinc-500">{caps.note}</p>
          </section>

          {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
          {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{message}</div> : null}
          {testResult ? <ConnectionTestSummary result={testResult} /> : null}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-zinc-200 bg-zinc-50 px-5 py-3">
          <span className="text-xs text-zinc-400">Saving creates the catalog and storage references, then tests the saved configuration.</span>
          <div className="flex gap-2">
            <Button onClick={onClose}>{testResult ? "Close" : "Cancel"}</Button>
            <Button variant="primary" onClick={saveConnection} disabled={saving}>
              {saving ? "Saving & testing..." : isEditing ? "Update & test connection" : "Save & test connection"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ConnectionRow({
  icon,
  label,
  value,
  mono = false
}: {
  icon?: ReactNode;
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="flex items-center gap-2 text-zinc-500">
        {icon}
        {label}
      </dt>
      <dd className={`max-w-[32rem] truncate text-right text-zinc-800 ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

function ConnectionTestSummary({ result, compact = false }: { result: ConnectionTestResult; compact?: boolean }) {
  return (
    <div className={`${compact ? "mt-2" : "mt-4"} rounded-md border border-zinc-200 bg-white p-3`}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-zinc-900">Connection test</span>
        <Badge tone={testTone(result.status)}>{result.status}</Badge>
      </div>
      {!compact ? <p className="mb-3 text-xs text-zinc-500">{result.message}</p> : null}
      <div className="space-y-2">
        {result.components.map((component) => (
          <div key={`${component.name}-${component.message}`} className="flex items-start justify-between gap-3 text-xs">
            <span className="font-medium text-zinc-700">{component.name}</span>
            <span className="max-w-[70%] text-right text-zinc-500">{component.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConnectionSyncMenu({
  open,
  onOpenChange,
  testing,
  syncing,
  disabled,
  result,
  onTest,
  onSync,
  onForceSync
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  testing: boolean;
  syncing: boolean;
  disabled: boolean;
  result?: TableIndexRefreshResult;
  onTest: () => void;
  onSync: () => void;
  onForceSync: () => void;
}) {
  return (
    <div className="relative">
      <Button onClick={() => onOpenChange(!open)} disabled={disabled}>
        <RefreshCw size={14} className={syncing || testing ? "animate-spin" : ""} />
        Sync
        <ChevronDown size={14} />
      </Button>
      {open ? (
        <div className="absolute right-0 top-10 z-40 w-96 rounded-lg border border-zinc-200 bg-white p-3 text-left shadow-xl">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-zinc-900">Connection checks</div>
              <div className="text-xs text-zinc-400">Probe reachability, then sync table metadata</div>
            </div>
            {syncing || testing ? <Badge tone="warning">running</Badge> : null}
          </div>
          <div className="space-y-1">
            <button
              className="flex w-full items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-400"
              disabled={testing || syncing}
              onClick={onTest}
            >
              <span>
                <span className="block font-medium text-zinc-800">Test connection</span>
                <span className="block text-xs text-zinc-400">Catalog auth, database reachability, and linked storage</span>
              </span>
              <RefreshCw size={14} />
            </button>
            <button
              className="flex w-full items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-400"
              disabled={testing || syncing}
              onClick={onSync}
            >
              <span>
                <span className="block font-medium text-zinc-800">Sync metadata</span>
                <span className="block text-xs text-zinc-400">Incremental catalog tables and Iceberg metadata</span>
              </span>
              <RefreshCw size={14} />
            </button>
            <button
              className="flex w-full items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-400"
              disabled={testing || syncing}
              onClick={onForceSync}
            >
              <span>
                <span className="block font-medium text-zinc-800">Force full metadata sync</span>
                <span className="block text-xs text-zinc-400">Re-read unchanged metadata pointers</span>
              </span>
              <RefreshCw size={14} />
            </button>
          </div>
          {syncing || testing ? <SyncProgress label={syncing ? "Sync in progress" : "Connection test in progress"} /> : null}
          {result ? <SyncSummary result={result} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function SyncProgress({ label }: { label: string }) {
  return (
    <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="font-medium">{label}</span>
        <span className="text-xs">running</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/70">
        <div className="h-full w-2/3 animate-pulse rounded-full bg-amber-500" />
      </div>
      <div className="mt-3 space-y-2">
        <SyncStage label="Catalog tables" progress={70} />
        <SyncStage label="Iceberg metadata files" progress={55} />
        <SyncStage label="Metadata cache" progress={35} />
      </div>
    </div>
  );
}

function SyncStage({ label, progress }: { label: string; progress: number }) {
  return (
    <div className="grid grid-cols-[8rem_1fr_2.5rem] items-center gap-2 text-xs">
      <span>{label}</span>
      <div className="h-1 overflow-hidden rounded-full bg-white/70">
        <div className="h-full rounded-full bg-current" style={{ width: `${progress}%` }} />
      </div>
      <span className="text-right font-mono">{progress}%</span>
    </div>
  );
}

function SyncSummary({ result }: { result: TableIndexRefreshResult }) {
  const failed = result.failed_table_count > 0 || result.errors.length > 0;
  return (
    <div className={`mt-3 rounded-md border p-3 text-sm ${failed ? "border-red-200 bg-red-50 text-red-800" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium">{failed ? "Metadata sync failed" : "Metadata sync complete"}</span>
        <span className="font-mono text-xs">{result.table_count} tables</span>
      </div>
      <div className={`mt-1 text-xs ${failed ? "text-red-700" : "text-emerald-700"}`}>
        {result.parsed_table_count} parsed · {result.skipped_table_count} unchanged · {result.failed_table_count} failed · {result.removed_table_count} removed
      </div>
      <div className={`mt-1 text-xs ${failed ? "text-red-700" : "text-emerald-700"}`}>
        {result.parse_job_count} metadata reads · {result.worker_count} workers
      </div>
      {result.errors.length ? (
        <div className="mt-2 space-y-1 text-xs text-red-700">
          {result.errors.slice(0, 3).map((error, index) => (
            <div key={`${error.table ?? "table"}-${index}`}>
              {error.table ? `${error.table}: ` : null}
              {error.error}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function testTone(status: ConnectionTestResult["status"]) {
  if (status === "ok") return "healthy";
  if (status === "warning") return "warning";
  return "critical";
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  hint
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-xs text-zinc-500">{label}</span>
      <input
        className="w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm outline-none placeholder:text-zinc-300 focus:border-zinc-500"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
      {hint ? <span className="mt-1 block text-xs text-zinc-400">{hint}</span> : null}
    </label>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-xs text-zinc-500">{label}</span>
      <input
        type="password"
        className="w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm outline-none placeholder:text-zinc-300 focus:border-zinc-500"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete="off"
      />
    </label>
  );
}

function TextArea({
  label,
  value,
  onChange,
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-xs text-zinc-500">{label}</span>
      <textarea
        className="min-h-32 w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm outline-none placeholder:text-zinc-300 focus:border-zinc-500"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
    </label>
  );
}

function SetupStep({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <div className="text-sm font-medium text-zinc-900">{title}</div>
      <p className="mt-1 text-xs text-zinc-500">{body}</p>
    </div>
  );
}

function Choice({
  active,
  label,
  sub,
  compact = false,
  onClick
}: {
  active: boolean;
  label: string;
  sub?: string;
  compact?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md border px-3 py-2 text-left transition ${active ? "border-zinc-900 bg-zinc-50" : "border-zinc-200 hover:border-zinc-300"} ${compact ? "" : "min-h-20"}`}
    >
      <div className="text-sm font-medium text-zinc-900">{label}</div>
      {sub ? <div className="mt-1 text-xs text-zinc-400">{sub}</div> : null}
    </button>
  );
}

function Segmented({
  label,
  value,
  items,
  onChange
}: {
  label: string;
  value: string;
  items: Array<[string, string]>;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <div className="mb-1 font-mono text-xs text-zinc-500">{label}</div>
      <div className="flex rounded-md border border-zinc-300 p-0.5 text-sm">
        {items.map(([key, itemLabel]) => (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={`flex-1 rounded px-2 py-1 ${value === key ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"}`}
          >
            {itemLabel}
          </button>
        ))}
      </div>
    </div>
  );
}

function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="text-xs font-medium uppercase tracking-wide text-zinc-400">{children}</div>;
}

function linkedStoreForConnection(connection: CatalogConnectionRead, stores: ObjectStoreConnectionRead[]) {
  const storeId = asString(connection.settings.object_store_connection_id);
  if (!storeId) return null;
  return stores.find((store) => store.id === storeId) ?? null;
}

function formFromConnection(
  connection: CatalogConnectionRead | undefined,
  store: ObjectStoreConnectionRead | null | undefined,
  environments: EnvironmentRead[]
): FormState {
  if (!connection) {
    return {
      ...DEFAULT_FORM,
      envName: environments[0]?.name ?? ""
    };
  }
  const environment = environments.find((item) => item.id === connection.environment_id);
  const catalogAuth = objectSetting(connection.settings.catalog_auth);
  const storageSettings = store?.settings ?? {};
  const storageAuth = objectSetting(storageSettings.storage_auth);
  const jdbc = objectSetting(connection.settings.jdbc_options);
  return {
    ...DEFAULT_FORM,
    envName: environment?.name ?? "",
    name: connection.name,
    catalog: asCatalogType(connection.catalog_type),
    uri: connection.endpoint ?? "",
    warehouse: connection.warehouse ?? asString(storageSettings.warehouse) ?? "",
    store: asStoreType(store?.store_type ?? asString(connection.settings.storage)),
    region: store?.region ?? asString(connection.settings.region) ?? environment?.region ?? "",
    endpoint: store?.endpoint ?? asString(connection.settings.endpoint) ?? "",
    accessStyle: asAccessStyle(storageSettings.access_style ?? connection.settings.access_style),
    sse: asSse(storageSettings.server_side_encryption ?? connection.settings.server_side_encryption),
    kmsKeyArn: asString(storageSettings.kms_key_arn ?? connection.settings.kms_key_arn) ?? "",
    remoteSigning: Boolean(storageSettings.remote_signing ?? connection.settings.remote_signing),
    catalogAuth: asCatalogAuthType(catalogAuth.mode),
    catalogUsername: asString(catalogAuth.username) ?? "",
    catalogClientId: asString(catalogAuth.client_id) ?? "",
    catalogIdentity: asString(catalogAuth.identity) ?? "",
    catalogSecretReference: asString(catalogAuth.secret_reference) ?? "",
    jdbcSslMode: asJdbcSslMode(jdbc.sslmode),
    jdbcSslRootCert: asString(jdbc.ssl_root_cert) ?? "",
    jdbcApplicationName: asString(jdbc.application_name) ?? "iceyard",
    storageAuth: asStorageAuthType(storageAuth.mode),
    storageIdentity: asString(storageAuth.identity) ?? "",
    storageSecretReference: asString(storageAuth.secret_reference) ?? "",
    awsAccessKeyId: asString(storageAuth.aws_access_key_id) ?? ""
  };
}

function objectSetting(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown) {
  return typeof value === "string" ? value : undefined;
}

function asCatalogType(value: unknown): CatalogType {
  return CATALOGS.some(([key]) => key === value) ? (value as CatalogType) : "rest";
}

function asStoreType(value: unknown): StoreType {
  return STORES.some(([key]) => key === value) ? (value as StoreType) : "s3";
}

function asCatalogAuthType(value: unknown): CatalogAuthType {
  return CATALOG_AUTHS.some(([key]) => key === value) ? (value as CatalogAuthType) : "none";
}

function asStorageAuthType(value: unknown): StorageAuthType {
  return STORAGE_AUTHS.some(([key]) => key === value) ? (value as StorageAuthType) : "keyless";
}

function asJdbcSslMode(value: unknown): JdbcSslMode {
  const modes: JdbcSslMode[] = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"];
  return modes.includes(value as JdbcSslMode) ? (value as JdbcSslMode) : "prefer";
}

function asAccessStyle(value: unknown): FormState["accessStyle"] {
  return value === "path-style" ? "path-style" : "virtual-hosted";
}

function asSse(value: unknown): FormState["sse"] {
  return value === "s3" || value === "kms" || value === "dsse-kms" ? value : "none";
}

function catalogAuthSettings(form: FormState): Record<string, unknown> {
  if (form.catalogAuth === "basic") {
    const settings: Record<string, unknown> = {
      mode: form.catalogAuth,
      username: form.catalogUsername.trim()
    };
    if (form.catalogPassword.trim()) settings.password = form.catalogPassword.trim();
    return settings;
  }
  if (form.catalogAuth === "bearer") {
    return {
      mode: form.catalogAuth,
      ...(form.catalogBearerToken.trim() ? { bearer_token: form.catalogBearerToken.trim() } : {})
    };
  }
  if (form.catalogAuth === "oauth_client") {
    const settings: Record<string, unknown> = {
      mode: form.catalogAuth,
      client_id: form.catalogClientId.trim()
    };
    if (form.catalogClientSecret.trim()) settings.client_secret = form.catalogClientSecret.trim();
    return settings;
  }
  if (form.catalogAuth === "aws_iam") {
    return { mode: form.catalogAuth, identity: form.catalogIdentity.trim() };
  }
  if (form.catalogAuth === "secret_ref") {
    return { mode: form.catalogAuth, secret_reference: form.catalogSecretReference.trim() };
  }
  return { mode: "none" };
}

function jdbcOptions(form: FormState): Record<string, unknown> | undefined {
  if (form.catalog !== "jdbc") return undefined;
  return {
    sslmode: form.jdbcSslMode,
    ssl_root_cert: form.jdbcSslRootCert || undefined,
    application_name: form.jdbcApplicationName || "iceyard"
  };
}

function storageAuthSettings(form: FormState): Record<string, unknown> {
  if (form.storageAuth === "static_key") {
    const settings: Record<string, unknown> = {
      mode: form.storageAuth,
      aws_access_key_id: form.awsAccessKeyId.trim()
    };
    if (form.awsSecretAccessKey.trim()) {
      settings.aws_secret_access_key = form.awsSecretAccessKey.trim();
    }
    if (form.awsSessionToken.trim()) settings.aws_session_token = form.awsSessionToken.trim();
    return settings;
  }
  if (form.storageAuth === "secret_ref") {
    return { mode: form.storageAuth, secret_reference: form.storageSecretReference.trim() };
  }
  if (form.storageAuth === "keyless") {
    return { mode: form.storageAuth, identity: form.storageIdentity.trim() };
  }
  return { mode: "credential_vending" };
}

function catalogAuthRefForSave(
  form: FormState,
  initialConnection: CatalogConnectionRead | undefined
) {
  if (form.catalogAuth === "secret_ref") {
    return form.catalogSecretReference || null;
  }
  if (
    initialConnection &&
    (form.catalogAuth === "basic" ||
      form.catalogAuth === "bearer" ||
      form.catalogAuth === "oauth_client")
  ) {
    return initialConnection.auth_ref;
  }
  return null;
}

function storageAuthRefForSave(
  form: FormState,
  initialObjectStore: ObjectStoreConnectionRead | null | undefined
) {
  if (form.storageAuth === "secret_ref") {
    return form.storageSecretReference || null;
  }
  if (initialObjectStore && form.storageAuth === "static_key") {
    return initialObjectStore.auth_ref;
  }
  return null;
}

function credentialValidationError(form: FormState, isEditing: boolean) {
  if (form.catalogAuth === "basic" && !form.catalogUsername) {
    return "Catalog username is required.";
  }
  if (form.catalogAuth === "basic" && !isEditing && !form.catalogPassword) {
    return "Catalog username and password are required.";
  }
  if (form.catalogAuth === "bearer" && !isEditing && !form.catalogBearerToken) {
    return "Catalog bearer token is required.";
  }
  if (form.catalogAuth === "oauth_client" && !form.catalogClientId) {
    return "Catalog OAuth client id is required.";
  }
  if (form.catalogAuth === "oauth_client" && !isEditing && !form.catalogClientSecret) {
    return "Catalog OAuth client id and client secret are required.";
  }
  if (form.catalogAuth === "secret_ref" && !form.catalogSecretReference) {
    return "Catalog secret reference is required.";
  }
  if (
    form.catalog === "jdbc" &&
    (form.jdbcSslMode === "verify-ca" || form.jdbcSslMode === "verify-full") &&
    !form.jdbcSslRootCert.trim()
  ) {
    return "JDBC verify-ca and verify-full require the database root CA certificate.";
  }
  if (form.storageAuth === "static_key" && !form.awsAccessKeyId) {
    return "AWS access key id is required.";
  }
  if (form.storageAuth === "static_key" && !isEditing && !form.awsSecretAccessKey) {
    return "AWS access key id and secret access key are required.";
  }
  if (form.storageAuth === "secret_ref" && !form.storageSecretReference) {
    return "Storage secret reference is required.";
  }
  return null;
}

function storageAuthNote(auth: StorageAuthType) {
  if (auth === "credential_vending") {
    return "No storage secret is stored here. The selected catalog is expected to vend scoped credentials at runtime.";
  }
  if (auth === "keyless") {
    return "No secret is stored. The worker uses the configured identity or the runtime credential chain.";
  }
  if (auth === "secret_ref") {
    return "Only the external reference is stored. Secret material stays in your secret manager.";
  }
  return "The secret access key is accepted once, stored as a secret reference, and never returned by API responses.";
}

function catalogUriLabel(catalog: CatalogType) {
  if (catalog === "jdbc") return "JDBC catalog DB URI";
  if (catalog === "hive") return "thrift uri";
  if (catalog === "glue") return "glue catalog id";
  if (catalog === "s3_tables") return "table bucket ARN";
  if (catalog === "hadoop") return "warehouse path";
  return "catalog endpoint";
}

function catalogHelp(catalog: CatalogType) {
  if (catalog === "jdbc") {
    return "Use the PostgreSQL/MySQL JDBC URI for the Iceberg catalog metadata database, for example jdbc:postgresql://host:5432/iceberg_catalog.";
  }
  if (catalog === "rest") {
    return "Use the REST catalog endpoint. This can be Polaris, Unity, Lakekeeper, or a generic Iceberg REST catalog.";
  }
  if (catalog === "glue") {
    return "Use the AWS account/catalog id and configure IAM or Lake Formation access through the auth section.";
  }
  if (catalog === "hive") {
    return "Use the Hive Metastore Thrift endpoint. Storage access is configured separately below.";
  }
  if (catalog === "nessie") {
    return "Use the Nessie API endpoint. Branching is catalog-level, while table storage remains configured below.";
  }
  if (catalog === "s3_tables") {
    return "Use the S3 Tables bucket ARN. The provider manages parts of the catalog and maintenance path.";
  }
  return "Use the filesystem warehouse path for local or development catalogs.";
}

function capabilityLabels(capabilities: Record<string, unknown>) {
  const labels = [
    ["supports_credential_vending", "Credential vending"],
    ["supports_remote_signing", "Remote signing"],
    ["supports_multi_table_commit", "Multi-table commits"],
    ["supports_server_side_scan_planning", "Scan planning"],
    ["supports_branches_tags", "Branch / tag ops"],
    ["can_create_v3", "Format v3"]
  ] as const;
  return {
    good: labels.filter(([key]) => capabilities[key] === true).map(([, label]) => label),
    bad: labels.filter(([key]) => capabilities[key] === false).map(([, label]) => label)
  };
}
