# Luma observability release review

Prepared October 13, 2026. Rollout was authorized after the final quality gate
passed. Gateway, runtime, monitoring and TTL are deployed and hosted acceptance
passed. The existing website, runtime identity, model, catalog,
quotas and scale-to-zero settings are preserved.

| Review item | Result |
|---|---|
| Root backend tests | 52 passed locally; two private-catalog tests skip when snapshots are absent in CI |
| Agent tests | 3 passed; 6 scaffold live integration tests intentionally skipped |
| Browser / frontend | 9 tests passed; production build passed |
| Vulnerabilities | Root, gateway, agent export and isolated evaluation requirements clean; npm audit clean |
| Synthetic security suite | 20 scenarios, 22 checks/turns passed |
| Final native offline grades | 14/14 complete, mean 4.86/5, minimum 4/5; safety 14/14 |
| Quality release gate | Passed after product-type guidance and evaluation-evidence corrections |
| Managed evaluation API | Failed with Google internal errors; supported native EvalTask fallback used |
| Performance baseline / final candidate | Identical seven local turns: 138.16 s / 29.42 s total |
| Paired semantic comparison | Complete: four ties, one candidate preference, two baseline preferences; additional option/clarifying wording investigated |
| Repeat warm p95 | Final concurrency 1: 2.52 s; initial concurrency 2: 12.60 s; six warm samples each |
| Hosted warm samples | 7/7 completed per run; p95 2.84 s at concurrency 1 and 2.51 s at concurrency 2 |
| Hosted trace / privacy | 26 connected gateway/agent spans, one root, no missing parents; checked content excluded |
| SSE failure / cleanup | Three controlled streamed errors counted as failures; support IDs and lease cleanup verified |
| Incidents / TTL | Internal-failure incident opened; five console-only policies; both TTL policies active, six legacy sessions backfilled |
| Terraform review | 31 changes; no deletes; same managed database and unrelated services untouched |
| Final infrastructure reconciliation | No changes after final rollout |
| Registry | One existing Luma match; registration unnecessary; invocation IAM remains private |
| Incremental estimate | $0–$4/month, conditional on uptime project allowance; $0.25–$2 one-off evaluation reserve |

The gateway image is built and pinned to its SHA-256 digest. Private plans, detailed synthetic transcripts,
audits and benchmark reports are in ignored `reports/`; the plan is
`infra/hardening.tfplan`. Public documentation contains only aggregate results.

Review [HARDENING.md](HARDENING.md), [THREAT_MODEL.md](THREAT_MODEL.md) and
[COSTS.md](COSTS.md). Previous artifacts/revisions are retained and the plan was
regenerated with the immutable gateway image. The same private runtime is updated;
only store monitoring/TTL changes are applied. Legacy expiry was backfilled after
activation. Detailed evidence remains private and synthetic.

The trace/SSE/incident checks passed. A hosted client disconnect released its lease,
but no cancellation-classified failure was observed. Isolated cloud cold-start
timing and actual telemetry billing have not been claimed as completed.
During correlation rollout the strict validator rejected valid SDK trace flags;
the gateway was temporarily returned to its working revision, repaired and rechecked.
Current traffic is 100% `beauty-store-api-00008-hhk`; the private agent source is
`114d104` and the gateway source is `b8e123b`. The shopping-code fingerprint graded
offline is unchanged. See HARDENING.md for digest, measurements and rollback.
TTL deletion cannot be undone.
