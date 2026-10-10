# Deploying a fork

This is a working reference deployment, not a fully parameterized multi-project
template. Public resource/project IDs are configuration, not credentials. A clone
does not grant access. Do not run deployment scripts against `sitiosweb1` unless
you administer it.

Replace `sitiosweb1` and derived names consistently before your own deployment:

| Location | Adapt |
|---|---|
| `beauty/cloud.py`, `beauty/catalog.py` | Model, Firestore and Storage projects |
| `gateway/main.py` | Firebase project, runtime regex and regional endpoint |
| `frontend/src/api.ts` | Firebase project/auth domain |
| `infra/main.tf` | Provider/billing project, region, bucket, budget currency/amount |
| `scripts/agents_cloud.py` | CLI credentials/quota project |
| `scripts/deploy_cloud.py` | Project/site, image tag, catalog fingerprint, runtime prefix |
| `scripts/deploy_hosting.py` | Hosting project/site |
| `scripts/publish_catalog.py` | Storage/Firestore project and bucket |
| `scripts/verify_cloud*.py` | Gateway/storefront target URLs |
| `cloudbuild.gateway.yaml` | Container repository/project and tag |
| `.env.example`, `agent/.env.example` | Environment project values |
| Agent manifest/eval config | Scaffold project settings where applicable |

Use `rg -n sitiosweb1` to find remaining references. Keep model location `global`
unless model support requires another location. Runtime region and API/resource
validation must match. Never assume setting one environment variable replaces all
fixed reference values.

The helper expects Terraform at `.tools/terraform/terraform.exe`; install there
or adapt its path. Standard Terraform can use ignored `infra/terraform.tfvars`.
Initialize a separate environment; never reuse another project's state blindly.

Helper plans require `LUMA_BILLING_ACCOUNT`. Database creation defaults to false;
use `LUMA_CREATE_FIRESTORE=true` only for a project with no existing database.
Replace the helper's catalog fingerprint and image tag with your actual import/
build values; these are not automatically discovered. Reference budget is MXN 180;
adapt currency/thresholds. Keep real environment config, state/plans, metadata and
tokens out of Git. Follow [the deployment runbook](DEPLOYMENT.md).
