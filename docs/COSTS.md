# Operating costs — checked October 9, 2026

The user authorized deployment October 9, 2026. Cloud foundations, the API gateway
and Firebase storefront are deployed. Luma is live on Agent Runtime; resource IDs
and production verification are in `docs/LIVE.md`.
The billing account uses MXN. The deployed project-wide budget is MXN 180/month,
with alerts at MXN 90 / 144 / 180 (roughly USD 5 / 8 / 10 using the planning rate
of MXN 18/USD; actual billing conversion may differ). Existing project costs count.
The catalog now contains 100 real skincare products from the Amazon 2023 dataset.
Seven live evaluation turns after requiring catalog retrieval used 12,209 input
tokens, 681 output tokens and 191.2 seconds locally: about 1,744 input / 97 output
tokens and 27.31 seconds per turn, including local credential overhead.
At the listed prices, extrapolating this small set to 100 ten-turn conversations
gives **$0.58 model charges**, or **$1.50 model + runtime** if runtime allowances are
already consumed. It excludes gateway, storage, query embeddings and other costs.
This is a small local evaluation, not a long-conversation or deployed runtime
measurement. Keep the conservative **$3–$6/month allowance** below until production
metrics are available. See `reports/cost-estimate.json` and `shopping-evaluation.json`.

| Monthly conversations (10 turns each) | Model tokens | Agent Runtime, available free tier | Model + runtime, no free tier | Suggested total allowance |
|---|---:|---:|---:|---:|
| 0 | $0 | $0 | $0 | $0–$1 at little traffic |
| 100 | $2.15 | $0 | $2.49 | **$3–$6** |
| 1,000 | $21.50 | $0.10 | $24.86 | $25–$35 |

Only the 100-conversation tier is enabled in code. Higher rows show hypothetical scale,
not a service entitlement. Free allowances are shared with other eligible usage on the
billing account; Firestore allowances apply to the eligible existing database.

## Formula

Per shopper message assume 5,000 input tokens **across all model calls**, 600 output
tokens including reasoning, and 10 seconds active runtime with 1 CPU / 4 GiB RAM.
Replayed conversation history, instructions, tool declarations and returned evidence
all count as inputs. Gemini 3.1 Flash-Lite global pricing: $0.25/M input, $1.50/M output.
Runtime: $0.085/vCPU-hour and $0.009/GiB-hour beyond 50 vCPU-hours / 100 GiB-hours monthly.

The implementation bounds one turn at 3 model calls, 12,000 cumulative input tokens,
600 output tokens per call, and 4 tool calls. The configured 1,000-turn monthly limit
therefore bounds model generation charges at approximately **$5.70** at these rates.
This does **not** cap the entire Google Cloud bill: embeddings, gateway requests,
storage, bandwidth, authentication, logs, build costs and other project services remain separate.
Failed attempts consume allowance because model work may already have happened.

For 100 descriptions of roughly 500 tokens each, initial embeddings at $0.15/M
tokens are about $0.0075; query embeddings for 1,000 short queries are also pennies.
Translation and repeated evaluation/judge calls incur separate token charges.
Initial small build, import and validation budget: **$0–$3**, excluding labor and paid data.
Inspect container registry size: the generated Python agent image may exceed its free
storage allowance. Configure image retention before repeated deployments.

## Update from measured usage

After import, run `python -m scripts.evaluate_shopping`, then
`python -m scripts.cost_estimate --usage-report reports/shopping-evaluation.json`.
The report averages successful turns; inspect failed-call usage and allow a margin.
Also grade the agent with the scaffolded `agents-cli eval` rubric before deployment.

Firebase Hosting and Cloud Run can fit within their free allowances at this demo scale,
but page views and image bandwidth are independent of conversation count. Minimum
instances are zero, so idle runtime compute scales down; cold starts are possible.
Use the default Hosting URL initially. A custom domain, taxes, licensed product data,
and costs of existing services in sitiosweb1 are excluded.

Project-wide approximate $5/$8/$10 budget alerts are deployed in MXN. Because sitiosweb1
already hosts other services, those alerts include **all project costs**. They are
notifications; the application counters enforce the chat allowance.

Sources:
- https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing
- https://cloud.google.com/products/gemini-enterprise-agent-platform/pricing
- https://docs.cloud.google.com/free/docs/free-cloud-features
- https://firebase.google.com/pricing
- https://cloud.google.com/run/pricing

## Observability candidate: additional cost

Estimate checked October 13, 2026: **$0–$4/month additional**, targeting less than
$5 at the existing 1,000-turn cap and modest browsing. This is an estimate, not a
billing cap. Reserve **$0.25–$2 one time** for the bounded synthetic evaluation;
continuous grading is disabled. Existing shopping/model costs remain separate.

Seven instrumented local agent turns produced 72 metadata records totaling 10,854
bytes, approximately 1.5 KiB/turn, before cloud envelopes and gateway logs. Budget
0.1 GiB/month of logs, 50,000 spans, and a conservative 12 MiB of sparse log-based
metric ingestion. At paid rates these are approximately $0.05, $0.01 and $3.10.
Allow another $0.75 for health requests, telemetry CPU and small storage/Firestore
changes: approximately **$3.91/month even if account-wide metadata allowances
are consumed**. Actual log-metric bytes and CPU cannot be established until rollout.

Cloud discovery found no existing active uptime checks and zero recorded check
executions month-to-date on October 13. One five-minute check at
six locations gives approximately 51,840 executions/month, within the project's
one-million free executions. Previously deleted checks or future unrelated checks
could consume that allowance. If exhausted, uptime alone adds about $15.55/month;
revise monitoring before rollout in that case. Listing checks does not fully verify
project-wide billing/shared allowances. No account-wide trace/metric allowance is
assumed in the paid-metadata estimate.

Native Google resource metrics are reused without a separate hosted metrics server.
Current alert policy pricing begins no sooner than September 1, 2027; reassess
before that date. Shared log retention and project budget thresholds are unchanged.
Extended retention, unusual browsing/abuse, build artifacts, taxes and unrelated
services remain outside this estimate. `python -m scripts.hardening_cost` writes
an ignored machine-readable estimate; reconcile it after a representative hosted day.
[Google Observability pricing](https://cloud.google.com/products/observability/pricing).
