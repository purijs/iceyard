# Iceyard — Performance, Layout & Lifecycle Automations

This document describes the automation features added on top of the core control plane,
their APIs, and runtime status.

## Shared subsystems

| Subsystem | Module | What it does | Status |
|---|---|---|---|
| S1 · Layout & stats model | `layout/` | Per-table physical profile (small-file ratio, delete density, metadata weight, partition skew, per-column clustering depth) derived from synced metadata | Derived from synced metadata; clustering depth & skew are clearly-labelled heuristics until per-file bounds come from a live catalog |
| S4 · Policy schema | `policies/` | Declarative `AutomationPolicy` (selector / trigger / action / guardrails / alerting) with CRUD + selector resolution | Real CRUD + audit; reconciliation/scheduling not yet executed |
| S2 · Workload profile | `advisor/` | Predicate/join/group-by signal for predicate-aware advice | Hints-based only; engine query-log ingestion is a documented future adapter |
| S3 · Before/after harness | — | Projection lives in the what-if engine; replay needs a real engine | Projection only |

## Feature endpoints

All endpoints are under `/api/v1` and require auth. Reads use `tables.read`; policy
mutations use `operations.manage`; WAP runs use `operations.execute`.

| # | Feature | Endpoint | Class | Notes |
|---|---|---|---|---|
| S1 | Layout profile | `GET /tables/{id}/layout-profile` | READ | Derived stats model |
| 2 | Layout what-if | `POST /tables/{id}/whatif` | READ | Projects files/bytes scanned for repartition / resort / refile-size |
| 1a | Clustering advisor | `POST /tables/{id}/clustering-advice` | READ | Ranks sort/z-order candidates; projects scan reduction |
| 1b | Materialized-view advice | `GET /tables/{id}/materialized-view-advice` | READ | Engine-native vs self-managed summary-table fallback |
| 3 | Parquet advice | `GET /tables/{id}/parquet-advice` | READ | Codec/level/row-group recommendation |
| 4 | Distribution advice | `GET /tables/{id}/distribution-advice` | READ | hash/range/none recommendation + ingestion hint |
| 6 | Retention simulation | `POST /tables/{id}/retention/simulate` | READ | Expiring snapshots, reclaimable bytes (estimate), earliest time-travel, protected exclusions |
| 8 | Cleanup (TTL) preview | `POST /tables/{id}/cleanup/preview` | READ | Estimated delete %, guardrail check, mode plan |
| 5 | Write-Audit-Publish | `POST /tables/{id}/wap/run` | METADATA/READ | Stages a branch, runs checks, publishes if green; creates a Job |
| S4 | Policies | `GET/POST/PATCH/DELETE /policies`, `GET /policies/{id}/match` | — | Declarative automation policies |

## New operation descriptors

Added to the registry (`operations/registry.py`), so they flow through the same
dry-run / gate / approval / audit pipeline and appear in the command palette, CLI, and API:

- `set_parquet_settings` (METADATA), `rewrite_parquet_encoding` (REWRITE)
- `set_write_distribution` (METADATA)
- `cleanup_old_data` (DESTRUCTIVE — dry-run, `max_delete_pct_guard`, restore point, approval)
- `backfill_default` (WRITE — affected-row estimate + restore point)
- `create_summary_table` (WRITE), `refresh_summary_table` (REWRITE)

## Runtime status

- **Implemented:** API surface, request/response validation, RBAC gating, audit events, policy
  CRUD + selector resolution, Job creation for WAP, all scoring/projection math over the
  synced metadata, and the safety classification of every new operation.
- **Projected:** reclaimable bytes, delete %, and clustering depth are estimates over
  synced metadata unless a compatible live runtime provides measured results.
  Heavy operation execution remains disabled until a compute backend is configured.
- **Not built yet:** engine query-log ingestion (S2), policy reconciliation/scheduling,
  S3 replay measurement, and engine-native MV creation (only the self-managed fallback is
  modelled).

## Safety

Destructive automations (`cleanup_old_data`) require dry-run, a restore point, approval,
and the `max_delete_pct` guardrail — the cleanup preview returns `guardrail_passed=false`
when a misconfigured cutoff would exceed the threshold. Retention expiry excludes
protected/tagged snapshots and reports them as `protected_excluded`.
