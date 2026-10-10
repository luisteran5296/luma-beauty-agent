# Luma shopping agent

Google ADK agent scaffolded by google-agents-cli 1.9.0, deployed on Agent Runtime.
Model: Gemini 3.1 Flash-Lite through Vertex AI, location global.

`app/agent.py` defines instructions/tools/controls; `app/shopping.py` runs bounded
turns and validates IDs. `app/shopping_routes.py` mounts the custom stream in
`app/fast_api_app.py`. `app/app_utils/` retains ADK/A2A/reasoning-engine adapters.

`search_products` retrieves filtered evidence; `get_product` returns details.
A turn without evidence must search. Guards limit model/tool/token usage and
require grounded IDs. Gateway supplies canonical card prices/URLs.

Run `python -m scripts.stage_agent` from root before isolated installation/deploy;
it copies shared `beauty/` into this package. Then `agents-cli install` and
`uv run pytest tests/unit tests/integration` here. Live tests are opt-in and paid.

Website histories live in gateway Firestore and populate ephemeral ADK sessions;
they do not appear in managed Sessions UI. Registry registration is not implemented.
The private runtime receives IAM-authenticated gateway calls.

See [architecture](../docs/ARCHITECTURE.md), [deployment](../docs/DEPLOYMENT.md),
[setup](../docs/LOCAL_SETUP.md), [API](../docs/API.md), and [live resources](../docs/LIVE.md).
Generated `deployment/` Terraform is scaffold material; actual infrastructure is
defined in `../infra/`.
