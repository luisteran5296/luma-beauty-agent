def test_production_keeps_shopping_and_adapters_without_debug_routes(monkeypatch):
    import importlib
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY', 'false')
    from app import fast_api_app
    module = importlib.reload(fast_api_app)
    paths = set(module.app.openapi()['paths'])
    assert {'/shop/stream', '/health', '/api/reasoning_engine', '/api/stream_reasoning_engine'} <= paths
    assert all(path.startswith(('/shop/', '/health', '/api/reasoning_engine', '/api/stream_reasoning_engine')) for path in paths)
    assert not any(getattr(route, 'path', '') in {'/docs', '/redoc', '/openapi.json'} for route in module.app.routes)


def test_private_trace_body_survives_proxy_header_rewrite(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from opentelemetry import trace
    from app import shopping_routes
    received = []
    async def respond(payload):
        received.append(trace.get_current_span().get_span_context().trace_id)
        yield {'type':'status','message':'Synthetic trace check'}
    monkeypatch.setattr(shopping_routes,'respond',respond)
    app = FastAPI()
    app.include_router(shopping_routes.router)
    original = '00-'+'a'*32+'-'+'b'*16+'-01'
    rewritten = '00-'+'c'*32+'-'+'d'*16+'-01'
    with TestClient(app) as client:
        response = client.post('/shop/stream',headers={'traceparent':rewritten},json={
            'message':'synthetic','catalog_version':'e'*64,'traceparent':original})
    assert response.status_code==200
    assert received==[int('a'*32,16)]
