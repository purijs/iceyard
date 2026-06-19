# Iceyard

Iceyard is an Apache Iceberg control-plane application for browsing table metadata, scoring table health, preparing governed operations, and tracking jobs and audit events.

## Repository Layout

```text
apps/api   FastAPI service
apps/web   Next.js console
infra      Deployment support
scripts    Local helper scripts
```

## Requirements

- Python 3.12+
- Node.js 20+
- SQLite for local development
- PostgreSQL for production-style deployments

## Local Development

```bash
make api-install
make web-install
make api-dev
make web-dev
```

API: `http://localhost:8000`

Web: `http://localhost:3000`

On first launch, bootstrap the initial workspace and platform admin from the web login screen or with:

```bash
curl -X POST http://localhost:8000/api/v1/auth/bootstrap \
  -H 'content-type: application/json' \
  -d '{"workspace_name":"Iceyard","email":"admin@example.com","password":"change-this-password","display_name":"Platform Admin"}'
```

## Verification

```bash
make api-test
make api-lint
make web-typecheck
make web-build
```

## Current Scope

The current implementation includes built-in auth, roles, audit logging, connection records, Iceberg table indexing, operation descriptors, dry-run records, approval requests, jobs, and a web console.

It also includes the performance/layout/lifecycle automations: a layout & stats model, layout what-if simulation, clustering and materialized-view advisors, Parquet and write-distribution tuning, retention/TTL simulation and cleanup, Write-Audit-Publish pipelines, and declarative automation policies. See [docs/automations.md](docs/automations.md) for the endpoints and runtime status.

Live catalog and execution adapters are intentionally behind interfaces; automation outputs are projections/heuristics over synced metadata unless a compatible runtime is configured.

### CORS

`ICEYARD_CORS_ORIGINS` lists allowed origins (default `http://localhost:3000`). In `local`/`test` mode, private-LAN origins (e.g. `http://192.168.x.x:3000`) are allowed automatically so the console works from another device. Set `ICEYARD_CORS_ORIGIN_REGEX` to override for staging/production.
