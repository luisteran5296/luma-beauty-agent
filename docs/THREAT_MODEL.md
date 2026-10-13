# Luma threat model

Scope: public storefront and authenticated anonymous chat gateway; private Agent
Runtime; store-specific Firestore/GCS data; logs, traces and synthetic reports.
Assets include quota/billing allowance, credentials, session privacy, catalog
integrity and the accuracy of canonical recommendation cards.

| Threat | Controls and evidence | Residual limitation |
|---|---|---|
| Anonymous quota abuse | Firestore transaction checks 100 conversations/month, 1,000 admitted attempts/month, ten turns/session and five turns/visitor/rolling minute | New anonymous identities bypass visitor throttle; global cap still holds. Public browsing and rejected traffic can incur cost. No edge DDoS protection |
| Cross-session reads/writes | Firebase token verification, server-derived UID, ownership check before history access, private database rules | Service accounts with existing broad project access remain privileged; this release does not audit unrelated identities |
| Replay/concurrent requests | Bounded request-ID history, atomic reservation and 120-second lease; failed/cancelled streams release leases | Failed admitted requests consume allowance. Abandoned requests may keep a lease until expiry |
| Shopper/catalog prompt injection | Untrusted-data instructions, forced initial retrieval, bounded tools/model calls, strict response schema and grounded IDs | LLM prose can still be misleading; deterministic IDs cannot prove every sentence. Synthetic quality grading is required |
| Invented facts/prices | API builds cards from canonical data, fails closed for unknown IDs or catalog fingerprint changes; missing evidence and rating limitations explicit | Historical descriptions are not independently verified; prices are snapshots |
| Credential exposure | Runtime IAM stays private; Cloud ADC/service identity, no downloaded keys; generic errors and credential scanner | Scanner is heuristic. Existing IAM breadth and compromised dependencies need separate review |
| Sensitive telemetry | Content capture disabled twice, exporter metadata allowlist, all events/links/status text stripped, sanitized JSON logs | Provider access/audit/build logs have separate platform retention. Query embedding keys temporarily exist in bounded process memory |
| Stale session access | 30-day TTL plus synchronous expiry check, legacy timestamp guard and reviewed TTL backfill | Asynchronous deletion is delayed; expired data remains stored until deletion. Rollback cannot restore deleted documents |
| Downstream failure | 90-second inference timeout, strict runtime events, sanitized correlated SSE errors, no partial history, failure metrics | Telemetry delivery is best-effort. Scale-to-zero cold starts and external model outages remain |

Tests cover content exclusion, exporter errors, server-owned trace IDs/propagation,
ownership/replay, cache/client concurrency, throttling, legacy/current expiry,
unknown IDs, malformed usage, catalog mismatch, truncation and cancellation.
Production debug routes are removed; health and required runtime adapters remain.

This release does not add payments, edge protection, managed Sessions migration,
continuous model grading, paid Security Command Center, Model Armor, external
observability vendors, enterprise certification, or an uptime guarantee.
