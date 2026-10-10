# Luma Beauty · AI shopping agent

An English demo store with **100 real skincare products** and a catalog-grounded
shopping assistant deployed on **Google Agent Runtime** through Google's
[`agents-cli`](https://github.com/google/agents-cli).

**[Live demo](https://sitiosweb1-luma-beauty.web.app)** ·
[Architecture](docs/ARCHITECTURE.md) · [Setup](docs/LOCAL_SETUP.md) ·
[Deployment](docs/DEPLOYMENT.md) · [Costs](docs/COSTS.md)

This is a fake store: no payments, purchases, fulfillment, or live inventory.
Prices and aggregate ratings are a **2023 historical snapshot**. Luma uses original
branding and is not affiliated with Amazon, Walmart, or the featured brands.

## Features

- Marketplace navigation, search, category/budget filters, details and simulated cart.
- Centered AI chat with an animated Blobatar, thinking states, launcher transitions,
  keyboard focus handling, mobile layout and reduced-motion support.
- RAG using Gemini embeddings, in-memory similarity, keywords and hard filters.
- Grounded recommendation IDs; canonical product cards supplied by the API.
- Firebase anonymous authentication and transactional server quotas: 100
  conversations/month, 10 turns/session, 1,000 total attempted turns/month.
- Versioned catalog updates with atomic activation and 30-second cloud refresh.
  Updating products does not require redeploying the agent.
- Agent Runtime and Cloud Run scale to zero, with at most two instances each.

## Stack

| Layer | Technology |
|---|---|
| Storefront | React 19, TypeScript, Vite, Firebase Hosting, Blobatar |
| Gateway | Python, FastAPI, SSE, Cloud Run |
| Agent | Google ADK, agents-cli 1.9.0, Google Agent Runtime |
| Models | Gemini 3.1 Flash-Lite; gemini-embedding-001, 768 dimensions |
| Database | Firestore products, active pointer, session history and quotas |
| Retrieval files | Immutable products/vectors in private Cloud Storage |
| Provisioning | Terraform, Cloud Build, Firebase Hosting REST API |

## Run locally

Use Python 3.11–3.13, Node.js 22+, and PowerShell. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt uv google-agents-cli==1.9.0
.\.venv\Scripts\python.exe -m playwright install chromium
Push-Location frontend
npm ci
npx playwright install chromium
Copy-Item .env.example .env.local
Pop-Location
New-Item -ItemType Directory -Force reports | Out-Null
.\.venv\Scripts\python.exe -m scripts.select_amazon_dataset
.\.venv\Scripts\python.exe -m scripts.import_catalog data/amazon-2023/selected.json --require-100
.\scripts\run-local.ps1
```

Open [localhost:5173](http://127.0.0.1:5173). Downloaded records and embeddings are
not committed; the selector rebuilds the historical selection from upstream.
Verify source rights for your use, or supply a permitted catalog. Source access and
image availability can change; shortfalls fail instead of using invented products.

Import without `--embed` runs without model charges. Browsing works, but actual chat
needs Google Cloud credentials and embeddings: see [local setup](docs/LOCAL_SETUP.md).

## Documentation

| Guide | Contents |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Request flow, RAG, grounding and session boundaries |
| [Local setup](docs/LOCAL_SETUP.md) | Installation, credentials, variables and commands |
| [Catalog](docs/CATALOG.md) | Source fields, selection, imports, embeddings and rollback |
| [API](docs/API.md) | Products, chat authentication, SSE events and errors |
| [Deployment](docs/DEPLOYMENT.md) | Terraform, private Agent Runtime, gateway and Hosting |
| [Fork configuration](docs/FORKING.md) | Reference-project values to replace for your own deployment |
| [Operations](docs/OPERATIONS.md) | Health, logs, quotas, troubleshooting and retention |
| [Costs](docs/COSTS.md) | Assumptions, measured usage, allowances and alerts |
| [Live deployment](docs/LIVE.md) | Actual resources and agent console link |
| [Validation](docs/VALIDATION.md) | Completed tests and evaluation limitations |
| [Data sources](docs/DATA_SOURCES.md) | Provenance and collector limitations |
| [Security](SECURITY.md) | Credentials, access controls, privacy and reporting |
| [Contributing](CONTRIBUTING.md) | Development workflow and validation |
| [Third-party notices](THIRD_PARTY.md) | Scaffold, avatar, dependencies and data rights |

## Layout

```text
frontend/  React store, AI chat UI and browser tests
gateway/   Authentication, API, streaming and quota/session persistence
beauty/    Product schema, retrieval, catalog loader and immutable snapshots
agent/     agents-cli scaffold, ADK tools, guardrails and runtime adapters
scripts/   Collect, import, publish, evaluate, deploy and verify
infra/     Terraform for the store's infrastructure
data/      Blank import templates; downloaded catalogs remain ignored
tests/     Backend, catalog, quota and agent-control tests
docs/      Setup, architecture, deployment and operation guides
```

`agent/beauty/` is generated: run `python -m scripts.stage_agent` before isolated
agent installation/deployment. Generated Terraform under `agent/deployment/` is
scaffold material; `infra/` is what this demo uses. No workflow deploys automatically.

## Validation and costs

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
Push-Location frontend
npm run build
npm test
Pop-Location
```

Recorded October 9, 2026: 27 backend tests and 9 browser tests passed; seven live
catalog evaluation turns passed. Hosted auth, grounded chat, session isolation and
denied direct Firestore access were verified. See [validation](docs/VALIDATION.md).

Budget **USD 3–6/month for 100 ten-turn conversations**, with modest website traffic;
idle estimate USD 0–1/month. These are estimates, depend on shared free allowances,
and exclude existing project costs. Alerts notify; quotas enforce chat limits.
See [the calculation](docs/COSTS.md).

## License

Application source: [Apache-2.0](LICENSE). Third-party licenses remain applicable.
Product descriptions, images, trademarks and datasets are **not licensed by this
repository**; see [third-party notices](THIRD_PARTY.md).
