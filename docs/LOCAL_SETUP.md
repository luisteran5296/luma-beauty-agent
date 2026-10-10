# Local setup

Tested on Windows/PowerShell with Python 3.11–3.13 and Node.js 22+. Install Google
Cloud SDK for real chat. Unix users can use `.venv/bin/python` and start servers
manually; PowerShell deployment helpers are Windows-oriented.

Follow [README](../README.md) installation and selection steps. Actual products,
embeddings and reports are ignored. CSV headers are supplied in `data/`.

## Browse without model calls

Import permitted products without `--embed`. Start these in separate terminals:

```powershell
$env:ENVIRONMENT='development'
$env:LOCAL_DEV_AUTH='true'
.\.venv\Scripts\python.exe -m uvicorn gateway.main:app --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev
```

Copy `frontend/.env.example` to `.env.local` first. Its development bypass works
only in Vite development builds. Keep both servers on localhost.

## Enable actual local chat

The code targets reference project `sitiosweb1`. Use an authorized identity, or
adapt the project using [fork configuration](FORKING.md). Google Cloud SDK must
already be authenticated. CLI credentials use its active account unless
`GCLOUD_ACCOUNT` selects another. Tokens are captured in memory, never printed.

```powershell
$env:USE_GCLOUD_CREDENTIALS='true'
# Optional: $env:GCLOUD_ACCOUNT='your-authorized-account@example.com'
.\.venv\Scripts\python.exe -m scripts.import_catalog data/amazon-2023/selected.json --require-100 --embed
$env:LOCAL_AGENT='true'
$env:LOCAL_DEV_AUTH='true'
$env:ENVIRONMENT='development'
.\.venv\Scripts\python.exe -m uvicorn gateway.main:app --host 127.0.0.1 --port 8000
```

Start Vite separately. Alternatively `scripts/run-local.ps1` starts hidden local
processes and enables chat when the retrieval bundle exists. It prints process IDs;
stop those processes when finished. For the isolated agents-cli environment:

```powershell
.\.venv\Scripts\python.exe -m scripts.stage_agent
$env:PATH=(Resolve-Path '.venv/Scripts').Path + ';' + $env:PATH
Push-Location agent
agents-cli install
uv run pytest tests/unit tests/integration
Pop-Location
```

Live integration tests require `RUN_LIVE_INTEGRATION=true` and incur model charges.

## Environment variables

Examples are documentation; Python scripts do not all automatically load `.env`.
Export shell variables. Vite loads `frontend/.env.local`.

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` locally; `production` enables startup guards |
| `LOCAL_DEV_AUTH` | Local backend auth bypass, forbidden in cloud |
| `LOCAL_AGENT` | Run shopping ADK in the local gateway |
| `USE_GCLOUD_CREDENTIALS` | Opt into short-lived local CLI credentials |
| `GCLOUD_ACCOUNT` | Optional explicit gcloud identity |
| `GOOGLE_CLOUD_PROJECT` | SDK/ADK project; remaining fixed IDs are listed in FORKING |
| `GOOGLE_CLOUD_LOCATION` | `global` for this model |
| `GOOGLE_GENAI_USE_VERTEXAI` | `True` for Google Cloud model access |
| `CATALOG_BACKEND` | `firestore` in deployed services |
| `CATALOG_POINTER_PATH` | Local active pointer, default `data/active-catalog.json` |
| `CATALOG_PATH`, `RETRIEVAL_BUNDLE_PATH` | Optional pinned paths for evaluations |
| `AGENT_RUNTIME_RESOURCE` | Private runtime resource for gateway inference |
| `ALLOWED_ORIGINS` | Comma-separated browser origins |
| `VITE_API_BASE` | Gateway URL, empty locally to use Vite proxy |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_APP_ID` | Public web app config |
| `VITE_LOCAL_DEV_AUTH` | Frontend development-only bypass |
| `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY` | `false` in deployed demo |
| `LUMA_BILLING_ACCOUNT` | Local Terraform helper billing account; never commit |
| `LUMA_CREATE_FIRESTORE` | `true` only after confirming no existing database |
| `LUMA_RUNTIME_RESOURCE` | Deployment-helper fallback for runtime ID |

## Evaluate

```powershell
$env:USE_GCLOUD_CREDENTIALS='true'
.\.venv\Scripts\python.exe -m scripts.evaluate_shopping
.\.venv\Scripts\python.exe -m scripts.cost_estimate --usage-report reports/shopping-evaluation.json
```

Live evaluations incur charges; routine offline checks are backend pytest and
frontend tests. Raw reports may contain answers/catalog data and stay out of Git.
