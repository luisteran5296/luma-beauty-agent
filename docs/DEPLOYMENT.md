# Deployment runbook

Reference target **sitiosweb1**, region **us-central1**. Use your authorized identity.
For a different project, apply [fork configuration](FORKING.md) first.
The user approved deployment October 9, 2026 after reviewing the application and
costs. See `docs/LIVE.md` for the actual resource IDs and verification status.
The commands below document the deployment workflow; inspect current resources
before repeating provisioning.

## 1. Preflight after the catalog arrives

- Import exactly 100 real, complete products with English titles/descriptions and matching embeddings.
- Confirm public reuse of descriptions/image URLs. Broken images have an accessible fallback.
- Run backend/frontend checks, actual shopping evaluations and agents-cli behavior grading. Require every custom response-quality score >= 4/5, no invalid IDs, budget violations or unsupported factual claims.
- Update measured costs; verify billing/free allowances, region support, and the runtime API passthrough with the deployed service.
- Inspect existing Firestore/Datastore and Firebase/Identity Platform configuration before provisioning. The reference deployment now has these services enabled.
- Check that `sitiosweb1-beauty-store-catalog`, service accounts `beauty-store-agent` / `beauty-store-api`, Artifact Registry `beauty-store`, and Cloud Run `beauty-store-api` are unused or belong to this store.
- Use existing compatible Firestore `(default)` database with new `beauty_store_*` collections; set `create_firestore=true` only if no database exists. Never reset/migrate another app's database.
- Terraform uses ADC, while scripts can use the specifically selected gcloud account. Verify the ADC identity before applying; do not assume it matches gcloud's active identity.

## 2. Provision store foundations (after approval)

`infra/main.tf` is validated with Terraform 1.13.5 and Google provider 7.46.1.
It has no automatic deploy hooks. Configure `infra/terraform.tfvars` with billing
account, future Hosting origin, `create_firestore`, and eventually image/runtime/catalog IDs.
Keep real values out of version control. The optional `scripts.deploy_cloud` helper
requires `LUMA_BILLING_ACCOUNT`; `LUMA_CREATE_FIRESTORE` defaults to `false`.
Its Terraform path, catalog fingerprint and container tag are reference values:
review them before planning. It does not initialize Terraform automatically.

Use a staged Terraform apply because the gateway depends on the new runtime ID and
published catalog. First plan/apply only the store foundations: APIs, service accounts
and their IAM grants, catalog bucket/reader grants, optional database, Artifact Registry,
and budget alerts. Select those resource targets explicitly; inspect the plan to ensure
it creates only store resources. The project budget includes existing project services.
Do not apply the gateway until its actual runtime ID and catalog version are known.

Enable Firebase services in the existing project if needed. Inspect any existing auth
providers first and **merge** the anonymous sign-in setting rather than replacing auth
configuration. Create a separate Firebase web app named `Luma Beauty` and a Hosting
site `sitiosweb1-luma-beauty` (if unused). Do not deploy to an existing app's default site.
Register that site locally with target `beauty-store` in `.firebaserc` and preserve any
other Hosting targets. The repo's `firebase.json` deploys only that target.

Merge the namespaced reference rules in `firestore.rules` into existing rules only
after reviewing the full ruleset. A permissive catch-all elsewhere overrides denials;
do not assume the reference rules alone secure existing broad rules. The browser never
reads/writes this store's Firestore directly; Admin SDK uses service-account IAM.

Publish the catalog with application-default credentials authorized for this project:

```powershell
.\.venv\Scripts\python.exe -m scripts.publish_catalog --approved
```

This writes only versioned store objects and `beauty_store_*` collections. Save the
printed catalog version and paths; upload both snapshots before switching the pointer.

## 3. Deploy the Agent Runtime through agents-cli

Stage the shared library and resolve the scaffold's dependencies:

```powershell
.\.venv\Scripts\python.exe -m scripts.stage_agent
$env:PATH=(Resolve-Path '.venv/Scripts').Path + ';' + $env:PATH
Push-Location agent
agents-cli install
agents-cli deploy --project sitiosweb1 --region us-central1 --deployment-target agent_runtime --service-name luma-agent --service-account beauty-store-agent@sitiosweb1.iam.gserviceaccount.com --cpu 1 --memory 4Gi --min-instances 0 --max-instances 2 --concurrency 8 --update-env-vars "ENVIRONMENT=production,CATALOG_BACKEND=firestore,GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=false" --no-wait
Pop-Location
```

Grant the agent the namespaced pointer reader's required `roles/datastore.viewer`
(included in Terraform) along with bucket object read access. Run `deploy --dry-run` first and inspect its
read-only checks. Leave Agent Runtime IAM private; never grant public/allUsers access.
The gateway's Vertex role allows its service account to call the runtime. Review existing
project-wide Vertex grants to ensure another app's broadly privileged identity is not
unexpectedly exposed. Additional fine-grained runtime IAM can be tightened after verification.

Check `agents-cli deploy --status` after it finishes, preserving
`agent/deployment_metadata.json`. Extract `remote_agent_runtime_id`. Do not enable
long-term Memory Bank or generated full prompt/response logging for this demo.
The scaffold preserves ADK/A2A serving; the public gateway uses `/api/shop/stream`.
Test that passthrough path with IAM authentication before continuing.

## 4. Deploy the gateway and storefront

- Build `gateway.Dockerfile` from the repository root with Cloud Build or Docker; publish into `us-central1-docker.pkg.dev/sitiosweb1/beauty-store/api:VERSION`. Use a build configuration that explicitly names `gateway.Dockerfile`.
- Set Terraform `gateway_image`, `runtime_resource`, `catalog_version`, and `hosting_origin=https://sitiosweb1-luma-beauty.web.app`. Run a full plan, inspect changes, then apply.
- Gateway production startup requires matching embeddings and 100 records loaded from Firestore, Firebase token auth, and an Agent Runtime ID. `LOCAL_DEV_AUTH` must never be enabled in cloud.
- Set frontend production build variables `VITE_API_BASE` to the gateway URI and `VITE_FIREBASE_API_KEY`/`VITE_FIREBASE_APP_ID` to the store web-app config. Firebase's browser API key is public configuration, not a service-account credential. Restrict its allowed API use as appropriate.
- Build with `npm ci; npm run build` and deploy **only** `hosting:beauty-store` with Firebase CLI, project `sitiosweb1`. The Vite development bypass is ignored by production builds.
- Check mobile and desktop flows, Firebase anonymous auth, correct CORS origin, streaming, source-backed product cards, quota rejection, and cross-user isolation. Verify minimum/maximum instance settings on both services.
- Check real billing and per-turn metrics after the first few conversations. Logs contain token counts/latency and error types, not prompts, transcripts or authorization headers.

## 5. Deployment helper commands

These commands perform cloud writes when applying/publishing. The reference
project's initial deployment has already completed; review current plans before
repeating them. Set `LUMA_BILLING_ACCOUNT` privately and leave
`LUMA_CREATE_FIRESTORE` consistent with the existing Terraform state. If the database
is already represented by `google_firestore_database.store[0]`, keep it `true`;
setting it false proposes removing that managed resource. The hardening review
helper reads this existing state safely and refuses plans containing deletes.

```powershell
# After Terraform initialization and configuration review:
.\.venv\Scripts\python.exe -m scripts.deploy_cloud plan
# Review infra/foundations.tfplan, then:
.\.venv\Scripts\python.exe -m scripts.deploy_cloud apply
.\.venv\Scripts\python.exe -m scripts.deploy_cloud firebase
.\.venv\Scripts\python.exe -m scripts.publish_catalog --approved
.\.venv\Scripts\python.exe -m scripts.stage_agent
# Run the agents-cli deployment from section 3; wait for success before continuing.
# Build/push the gateway image from section 4 and confirm its tag in the helper.
.\.venv\Scripts\python.exe -m scripts.deploy_cloud plan-full
# Review infra/deployment.tfplan, then:
.\.venv\Scripts\python.exe -m scripts.deploy_cloud apply-full
.\.venv\Scripts\python.exe -m scripts.deploy_hosting
```

Firebase setup may return an asynchronous operation when adding Firebase or
creating its web app; wait for completion, then rerun to finish configuration.
The helper saves ignored public web config under `reports/` for Hosting builds.
`scripts.deploy_hosting` builds and releases only the configured dedicated site
using the Hosting REST API. Alternatively use Firebase CLI with the target in
section 4. Agents CLI wrapper `scripts.agents_cloud` uses the local gcloud identity
instead of assuming ADC matches it. Keep root `reports/` present for these helpers.

## 6. Refresh, rollback and retention

Manual refresh only. Import a validated 100-product catalog with `--embed`, then
publish it after deployment approval. Publication switches one Firestore active
pointer containing both immutable GCS paths. Both services refresh that pointer
every 30 seconds and cache complete snapshots by version; no code redeploy is needed
for catalog updates. The browser refreshes its current query every 30 seconds.
Keep previous immutable snapshots. Rollback changes the Firestore pointer back to a
previous version and both of its matching paths. A request during the brief propagation
window can fail the version guard rather than mix facts and recommendation cards.

Quota counters use the Mexico City calendar month. Failed requests consume quota;
request IDs prevent accidental replay, and a 120-second lease prevents overlapping
messages in one session. The API timeout is 90 seconds and Cloud Run timeout is 100.
The hardening candidate implements 30-day inactivity expiry and a reviewed TTL
backfill. Do not delete active monthly quota counters during cleanup.

This pilot's 100-conversation cap bounds model usage, not the entire cloud bill.
Unauthenticated page/API requests and excess traffic can still incur infrastructure charges.

## 7. Observability candidate rollout

See [HARDENING.md](HARDENING.md) for the concrete plan, measurements, private
evaluation reports and post-deployment checks. The command in section 3 describes
the previous release. For this candidate change the runtime telemetry flag to
`true` and add `ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false` and
`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT`. Custom sanitized
instrumentation uses one exporter; do not enable the scaffold exporter too.
Preserve min=0, max=2, the current model, catalog and private invocation IAM.
Build the reviewed gateway image, set `LUMA_GATEWAY_IMAGE` to its immutable tag,
then regenerate/review the full plan before apply. Do not apply the candidate
plan while its image is still unbuilt. CI never deploys this project.
