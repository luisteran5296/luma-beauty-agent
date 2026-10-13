# Luma observability release review

Prepared October 13, 2026. Code is a candidate; **no application or infrastructure
deployment has occurred**. The existing website, runtime identity, model, catalog,
quotas and scale-to-zero settings are preserved.

| Review item | Result |
|---|---|
| Root backend tests | 48 passed locally; two private-catalog tests skip when snapshots are absent in CI |
| Agent tests | 2 passed; 6 scaffold live integration tests intentionally skipped |
| Browser / frontend | 9 tests passed; production build passed |
| Vulnerabilities | Root, gateway, agent export and isolated evaluation requirements clean; npm audit clean |
| Synthetic security suite | 20 scenarios, 22 checks/turns passed |
| Final native offline grades | 12/14 quality grades, mean 4.75/5, minimum 4/5; safety 14/14; two Google judge deadlines remain after bounded retry |
| Quality release gate | Incomplete; all final-candidate grades must be present before rollout; earlier candidate passed 14/14 |
| Managed evaluation API | Failed with Google internal errors; supported native EvalTask fallback used |
| Performance baseline / candidate | Identical seven local turns: 138.16 s / 30.64 s total |
| Paired semantic comparison | Six native ties; one Google judge timeout remains ungraded after bounded retry |
| Repeat warm p95 | 13.39 s at concurrency 1; 12.60 s at concurrency 2; six samples each |
| Terraform review | 31 changes; no deletes; same managed database and unrelated services untouched |
| Registry | One existing Luma match; registration unnecessary; invocation IAM remains private |
| Incremental estimate | $0–$4/month, conditional on uptime project allowance; $0.25–$2 one-off evaluation reserve |

The candidate image is not built yet. Private plans, detailed synthetic transcripts,
audits and benchmark reports are in ignored `reports/`; the plan is
`infra/hardening.tfplan`. Public documentation contains only aggregate results.

Review [HARDENING.md](HARDENING.md), [THREAT_MODEL.md](THREAT_MODEL.md) and
[COSTS.md](COSTS.md). After approval, snapshot previous artifacts/revisions, build
immutable candidates, regenerate the plan with the verified image, update the same
private runtime, and apply store-only monitoring/TTL changes. Backfill legacy expiry.
Resolve the two missing final-candidate quality grades before deploying; approval
does not override this release gate.

Hosted trace correlation/content inspection, cold-start timing, SSE failure metrics,
lease cleanup, console incidents and actual telemetry billing are post-rollout
acceptance checks; they have not been claimed as completed. If a check fails,
restore the saved previous gateway/agent artifacts. TTL deletion cannot be undone.
