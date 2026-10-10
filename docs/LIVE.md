# Live deployment — October 9, 2026

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
- Gateway image: `us-central1-docker.pkg.dev/sitiosweb1/beauty-store/api:v3`.
- Agent configured minimum instances 0, maximum 2, 1 CPU / 4 GiB RAM.

Agent Runtime deployment succeeded. The locked dependencies include Firestore
and the container launches its installed Python environment directly. Both
dedicated accounts have API-consumption permission. The agent must call
`search_products` before answering when no current catalog evidence exists.
Truncated/error streams produce a clear gateway error and release the session.
Automatic ADK telemetry exporters are disabled; gateway logs retain usage/latency
metrics without prompt text. This avoids unused monitoring/logging exporter calls.

Storefront verified in a real browser: 100 cards, visible demo banner, no page errors,
mobile modal opens without viewport overflow. Gateway health returns 100 products.
Firebase anonymous login works, missing chat auth returns 401, and direct browser
access to the Firestore catalog pointer is denied. Root Python tests: 27 passed.
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
Agent Registry registration has not been performed.

For future imports, run the documented importer and `scripts.publish_catalog
--approved`. Both cloud services load the new matching catalog/index within 30 seconds.
Use `scripts.agents_cloud deploy --status` for runtime status and
`scripts.deploy_cloud plan-full` / `apply-full` to review and apply gateway changes.
Terraform state is local and ignored; retain `infra/terraform.tfstate` securely.
