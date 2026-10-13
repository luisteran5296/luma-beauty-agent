# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import os
import asyncio
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner

from app.app_utils import services
from beauty.telemetry import setup, shutdown
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.reasoning_engine_adapter import (
    attach_reasoning_engine_routes,
)

load_dotenv()
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)
# One process-wide provider/exporter with an allowlist sanitizer. ADK emits its
# native spans into this provider; do not also install the scaffold exporters.
setup('luma-agent')
otel_to_cloud = False

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from beauty.catalog import get_catalog

    await asyncio.to_thread(get_catalog)
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    try:
        yield
    finally:
        from beauty.cloud import shared_model_client
        if shared_model_client.cache_info().currsize:
            await shared_model_client().aio.aclose()
            shared_model_client().close()
        shutdown()


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=os.getenv('ENVIRONMENT') != 'production',
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=otel_to_cloud,
    lifespan=lifespan,
)
app.title = "luma-agent"
app.description = "API for interacting with the Agent luma-agent"

# Proxy routes so the Vertex AI Console Playground (reasoning_engine SDK) can
# talk to this agent alongside the native adk_api routes.
attach_reasoning_engine_routes(app)

from app.shopping_routes import router as shopping_router

if os.getenv('ENVIRONMENT') == 'production':
    # Runtime adapters above remain; interactive/debug/session mutation surfaces
    # are unnecessary for the website's stateless shopping path.
    app.router.routes[:] = [route for route in app.router.routes if
        getattr(route, 'path', '').startswith(('/shop/', '/a2a/', '/api/reasoning_engine', '/api/stream_reasoning_engine'))]

# FastAPI can defer include_router using an internal route wrapper without a
# path. Include the required shopping router after pruning development surfaces.
app.include_router(shopping_router)


@app.get('/health')
async def health():
    return {'status': 'ok'}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
