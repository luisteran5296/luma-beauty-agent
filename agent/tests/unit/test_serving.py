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
