# Operations

## Health and monitoring

Expect `/health` to return `status=ok`, 100 products, `agent_configured=true` and
the intended version. Inspect Cloud Run revisions and Agent Platform Deployments
in `us-central1`. `scripts.agents_cloud deploy --status` checks the configured
runtime. Keep ignored deployment metadata and Terraform state securely.

The observability candidate adds sanitized `chat_completed`, `chat_failed`,
`chat_rejected`, `guard_failure`, `quota` and `operation` JSON events and correlated
OpenTelemetry spans. It is pending reviewed rollout; the current deployment uses
the previous logging implementation. See [HARDENING.md](HARDENING.md) for console
locations, privacy controls, metric definitions, incident thresholds and validation.
Cloud provider access/build logs exist separately.

## Quotas and retention

`beauty_store_quotas` holds monthly counters; `beauty_store_sessions` holds bounded
history, anonymous UID, ownership and leases. Limits: 100 new conversations/month,
1,000 attempted turns/month, 10 turns/session. Months use Mexico City time.
Failed reservations after model work still consume allowance. A fresh browser/
anonymous identity cannot bypass global counters.

The hardening candidate enforces five admitted turns per visitor per rolling minute
in the same reservation transaction. Sessions expire after 30 days of inactivity;
the synchronous guard rejects expired history before TTL deletion completes.
Rollout enables Firestore TTL and backfills old timestamps without changing monthly
counters. Long-term Memory Bank stays disabled. This throttle is not edge DDoS
protection and does not stop visitors from creating new anonymous identities.

## Troubleshooting

| Symptom | Check |
|---|---|
| Catalog/index mismatch | Import a matching pair, preserve immutable snapshots |
| Refresh-related error | Wait 30 seconds for both services and retry |
| Chat 401 | Anonymous provider, web build config, refreshed ID token |
| Cloud 403 | Vertex/Firestore/Storage/API-consumption permissions |
| Chat 409 | Ownership, unique request ID, outstanding 120-second lease |
| Chat 429 | Server counters, next Mexico City monthly reset |
| Generic stream error | Gateway error class/runtime logs; incomplete streams fail |
| Model 404 | Global model location and current availability |
| Slow first request | Scale-to-zero cold start and model latency |
| Missing registry/sessions | Registry discovery confirms `luma-agent` in us-central1; website sessions are Firestore |
| Missing trace | Check both service env flags, trace-writer IAM, API enablement and exporter failure metadata |
| Slow warm requests | Component spans: embeddings, model, token counting, credential refresh and history persistence |
| Support error ID | Match `X-Request-ID` / SSE `request_id` to sanitized JSON logs; never ask for an auth token |
| Broken image | Source reachability; import a permitted replacement URL |

Inference timeout is 90 seconds; Cloud Run timeout 100. Diagnose before repeated
identical redeploys. Budget alerts notify; they do not stop cloud spending.

## Maintenance

`scripts.verify_cloud` and `scripts.verify_cloud_ui` perform real hosted API/browser
checks, create anonymous visitors and can consume paid model calls/demo allowance.
Run routine offline tests first. Catalog changes follow [CATALOG.md](CATALOG.md).
Retain versions for rollback and monitor billing/container registry storage.

To remove this store, inspect a targeted plan and dedicated runtime/Hosting site.
Do not destroy shared Firestore or disable project APIs as a shortcut. No automatic
teardown or production deployment workflow is installed.
