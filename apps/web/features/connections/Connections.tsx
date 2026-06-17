"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { Badge, Button, Panel } from "@/components/ui";
import type { CatalogConnectionRead, EnvironmentRead } from "@/types/api";

export function Connections({
  token,
  environments,
  connections,
  onRefresh
}: {
  token: string;
  environments: EnvironmentRead[];
  connections: CatalogConnectionRead[];
  onRefresh: () => Promise<void>;
}) {
  const [name, setName] = useState("dev-catalog");
  const [catalogType, setCatalogType] = useState("rest");
  const [endpoint, setEndpoint] = useState("https://catalog.example.com");
  const [error, setError] = useState<string | null>(null);

  async function createConnection() {
    setError(null);
    try {
      let env = environments[0];
      if (!env) {
        env = await api.createEnvironment(token, { name: "dev", kind: "dev", region: "eu-central-1" });
      }
      await api.createCatalogConnection(token, {
        environment_id: env.id,
        name,
        catalog_type: catalogType,
        endpoint,
        warehouse: "s3://dev-lakehouse"
      });
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create connection.");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-zinc-500">Catalog metadata remains the source of truth; the local index can be rebuilt from connected catalogs.</p>
      </div>
      <Panel title="Add connection">
        <div className="grid gap-3 md:grid-cols-4">
          <input className="rounded-md border border-zinc-300 px-3 py-2 text-sm" value={name} onChange={(event) => setName(event.target.value)} />
          <select className="rounded-md border border-zinc-300 px-3 py-2 text-sm" value={catalogType} onChange={(event) => setCatalogType(event.target.value)}>
            {["rest", "jdbc", "glue", "nessie", "hive", "hadoop", "custom"].map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <input className="rounded-md border border-zinc-300 px-3 py-2 text-sm" value={endpoint} onChange={(event) => setEndpoint(event.target.value)} />
          <Button variant="primary" onClick={createConnection}>
            Add connection
          </Button>
        </div>
        {error ? <div className="mt-3 text-sm text-red-700">{error}</div> : null}
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        {connections.map((connection) => (
          <Panel key={connection.id} title={connection.name} right={<Badge tone={connection.is_enabled ? "healthy" : "neutral"}>{connection.is_enabled ? "enabled" : "disabled"}</Badge>}>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">Catalog</dt>
                <dd className="font-mono text-zinc-800">{connection.catalog_type}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">Endpoint</dt>
                <dd className="max-w-sm truncate font-mono text-zinc-800">{connection.endpoint ?? "not set"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-500">Warehouse</dt>
                <dd className="max-w-sm truncate font-mono text-zinc-800">{connection.warehouse ?? "not set"}</dd>
              </div>
            </dl>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {Object.entries(connection.capabilities)
                .filter(([, value]) => value === true)
                .slice(0, 6)
                .map(([key]) => (
                  <Badge key={key} tone="healthy">
                    {key.replaceAll("_", " ")}
                  </Badge>
                ))}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
