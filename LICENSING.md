# Iceyard Licensing

Iceyard is **open-core**. Different parts of the repository are under different licenses,
and the running product behaves differently depending on its **edition**.

## Which license applies to what

| Path | License | Why |
|---|---|---|
| `apps/api/` server (control plane) | **Business Source License 1.1 (BSL)** | Source-available and self-hostable, but not resellable as a competing managed service. Converts to Apache 2.0 on the Change Date. |
| `apps/api/iceyard_api/operations/` (operation-descriptor registry) | **Apache 2.0** | The descriptor catalog is meant to become a de-facto standard, so it stays permissively licensed. |
| `apps/web/lib/`, `apps/web/types/` (client + API types / SDK surface) | **Apache 2.0** | Ecosystem/integration surface — connectors, CLI, Terraform should build on it freely. |
| Everything else | **BSL 1.1** | Default for the commercial control plane. |

The full Apache 2.0 text is in [`LICENSE-APACHE`](LICENSE-APACHE).

### BSL parameters (our terms)

- **Licensor:** Iceyard.
- **Licensed Work:** the Iceyard control-plane server (this repo, excluding the Apache-2.0 paths above).
- **Additional Use Grant:** you may run the Licensed Work in production for your own data,
  **but you may not offer it to third parties as a hosted/managed service that competes with
  Iceyard's commercial offering.**
- **Change Date:** four years after each version is published.
- **Change License:** Apache 2.0 (the code becomes fully open after the Change Date).

## Editions — GitHub (OSS) vs SaaS (iceyard.dev)

The same codebase serves three editions, selected by `ICEYARD_EDITION`
(`oss` | `cloud` | `enterprise`). This is how "what's on GitHub" differs from
"what's on iceyard.dev" without forking the code:

| Edition | Where it runs | Unlocks |
|---|---|---|
| `oss` (default) | Self-hosted from GitHub | Multi-catalog read + health scan, the operation catalog/GUI, core safe maintenance (compaction, expire, snapshot/rollback), jobs, audit, RBAC |
| `cloud` | iceyard.dev (hosted) | + layout what-if, clustering/format advisors, retention simulation, automation policies, WAP pipelines, autonomous optimization, FinOps ledger |
| `enterprise` | iceyard.dev / BYOC | + data-retention/TTL cleanup, compliance pack, disaster recovery, SSO/SCIM |

Gating is enforced server-side in `iceyard_api/editions`. A locked feature returns
HTTP 403 with an upgrade message; `GET /api/v1/edition` reports the active edition and the
feature matrix so the console can show locked features as upgrade prompts. Because the gate
is server-side, the public OSS build cannot simply flip a flag to unlock paid features —
the hosted SaaS sets the edition under Iceyard's control.

## Contributions

Contributions are accepted under the **DCO** (Developer Certificate of Origin) — a
`Signed-off-by` line, not a CLA — to keep contribution friction low while preserving the
right to relicense at the Change Date.

## What this means in plain terms

- **You can** read, audit, self-host, and use Iceyard in production for your own lakehouse.
- **You cannot** take the BSL-licensed server and resell it as a managed service that
  competes with Iceyard Cloud.
- **The registry and client SDK are fully open** (Apache 2.0) so the ecosystem can build on
  them without restriction.
- **After four years**, each released version becomes Apache 2.0.
