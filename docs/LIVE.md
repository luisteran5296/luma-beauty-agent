# Live deployment — October 13, 2026

Deployment was authorized in `sitiosweb1` using a project-authorized identity.

- Storefront: https://sitiosweb1-luma-beauty.web.app
- Gateway: https://beauty-store-api-cgbi4c4u5q-uc.a.run.app
- Region: us-central1
- Agent Runtime: `projects/719793696278/locations/us-central1/reasoningEngines/4860633318019825664`
- Console: https://console.cloud.google.com/vertex-ai/agents/agent-engines/locations/us-central1/agent-engines/4860633318019825664?project=sitiosweb1
- Catalog: 100 products, immutable snapshot `c11ba6e461c161c0d3db440b7e0a1deac79ef1f969245612a51e67253ac2861c`
- Private catalog bucket: `sitiosweb1-beauty-store-catalog`
- Firestore: newly provisioned `(default)` native database, store-specific collections.
- Agent account: `beauty-store-agent@sitiosweb1.iam.gserviceaccount.com`
- Gateway account: `beauty-store-api@sitiosweb1.iam.gserviceaccount.com`
- Firebase web app: `1:719793696278:web:e654a908cad7f613e48f37`; anonymous auth enabled.
- Billing alert budget: MXN 180, with 50%, 80%, 100% thresholds. Includes all project costs.
- Gateway minimum instances 0, maximum 2, 1 CPU / 512 MiB RAM.
- Gateway revision: `beauty-store-api-00008-hhk`, 100% traffic.
- Gateway image: `us-central1-docker.pkg.dev/sitiosweb1/beauty-store/api@sha256:697bcaada390cda0a1446d216727b9083d5aa3f52833ad4bbdabf1d875ebea21`.
- Agent configured minimum instances 0, maximum 2, 1 CPU / 4 GiB RAM.

Agent Runtime deployment succeeded. The locked dependencies include Firestore
and the container launches its installed Python environment directly. Both
dedicated accounts have API-consumption permission. The agent must call
`search_products` before answering when no current catalog evidence exists.
Truncated/error streams produce a clear gateway error and release the session.
Native ADK spans use one sanitized metadata-only OTLP exporter; duplicate scaffold
exporters are disabled. Gateway and private agent share server-controlled trace
context. Prompt/response capture is explicitly disabled. The deployed agent source
is `114d104`, runtime revision label `trace-flags-fix`; gateway source is `b8e123b`.

Storefront verified in a real browser: 100 cards, visible demo banner, no page errors,
mobile modal opens without viewport overflow. Gateway health returns 100 products.
Firebase anonymous login works, missing chat auth returns 401, and direct browser
access to the Firestore catalog pointer is denied. Root Python tests: 52 passed.
Production budget search and follow-up price/rating comparison passed with exact
catalog IDs and recommendations below USD 20. Another anonymous visitor cannot
reuse the first visitor's session (409). Unauthenticated runtime access is denied
(401). See `reports/cloud-smoke.json`.

The actual hosted browser chat returned three product cards in 9.33 seconds and
no page errors. See `reports/cloud-live-ui.json` and `reports/cloud-live-chat.png`.
All seven refreshed model evaluation turns passed, using 12,209 input / 681 output
tokens. Estimated budget remains USD 3–6/month for 100 ten-turn conversations.
Usage-based allowances are shared; validation attempts consume the demo quota.

Deployment helpers use the selected account's short-lived token in memory. No
service-account keys are created. Firebase deployment uses the documented Hosting
REST API and releases only this store's site. Other agents and budgets are preserved.

Shopping history and quota ownership live in `beauty_store_sessions` and
`beauty_store_quotas` in Firestore. They are separate from Agent Platform's managed
Sessions UI. Agent Runtime hosts the actual ADK tool/model runner; it is private.
Registry discovery confirmed one existing Luma entry; no duplicate was created.

The October 13 hardening acceptance found one connected 26-span trace with native
model/tool spans, no missing parents and no checked sensitive content. Controlled
SSE failures released leases and generated failure metrics/console incidents.
Both TTL policies are active; six legacy sessions were backfilled. All 14 native
offline quality grades completed (mean 4.86/5, minimum 4), with 14/14 safety passes.
Seven hosted turns per concurrency completed: p95 2.84 s at one client and 2.51 s
at two. Cloud cold starts were not isolated. Estimated additional observability
cost is $0–$4/month; actual billing is not yet measured.

[Luma dashboard](https://console.cloud.google.com/monitoring/dashboards/builder/00dcfaef-f0dc-47c6-9db3-d669d1d35ada?project=sitiosweb1),
[traces](https://console.cloud.google.com/traces/list?project=sitiosweb1),
[console incidents](https://console.cloud.google.com/monitoring/alerting?project=sitiosweb1).
See [release review](RELEASE_REVIEW.md) and [operating guide](HARDENING.md).

For future imports, run the documented importer and `scripts.publish_catalog
--approved`. Both cloud services load the new matching catalog/index within 30 seconds.
Use `scripts.agents_with_gcloud deploy --project sitiosweb1 --region us-central1 --status`
for runtime status, and `scripts.review_infrastructure` with the built immutable
`LUMA_GATEWAY_IMAGE` to review gateway changes. Apply only the reviewed saved plan.
Terraform state is local and ignored; retain `infra/terraform.tfstate` securely.
