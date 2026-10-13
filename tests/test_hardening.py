import json
import threading
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode
from beauty.telemetry import SafeExporter
from beauty.telemetry import AdmissionProcessor
from beauty.cache import TTLCache
from beauty.contracts import Turn, Result
from gateway.quota import MemoryQuota, LimitExceeded, SessionConflict, reserve_state
from beauty.catalog import Catalog
import gateway.main as gateway


def test_setup_supplies_required_otlp_project_resource(monkeypatch):
    import requests
    import google.auth
    import google.auth.transport.requests
    import beauty.telemetry as telemetry
    monkeypatch.setattr(telemetry,'_provider',None)
    monkeypatch.setattr(telemetry,'_service',None)
    monkeypatch.setenv('GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY','true')
    monkeypatch.setenv('LUMA_AGENT_ENGINE_ID','4860633318019825664')
    monkeypatch.setattr(google.auth,'default',lambda **kwargs:(None,'sitiosweb1'))
    monkeypatch.setattr(google.auth.transport.requests,'AuthorizedSession',lambda credentials:requests.Session())
    monkeypatch.setattr(telemetry.trace,'set_tracer_provider',lambda provider:None)
    telemetry.setup('luma-agent')
    provider = telemetry._provider
    try:
        assert provider.resource.attributes['gcp.project_id']=='sitiosweb1'
        assert provider.resource.attributes['gcp.vertex.agent.engine_id']=='4860633318019825664'
        assert set(provider.resource.attributes) <= telemetry.RESOURCES
    finally:
        provider.shutdown()


def test_exporter_removes_every_content_surface():
    class Capture:
        spans = []
        def export(self, spans): self.spans.extend(spans); return SpanExportResult.SUCCESS
        def shutdown(self): pass
    capture = Capture()
    provider = TracerProvider(resource=Resource({'service.name': 'test', 'session_id': 'SECRET'}))
    provider.add_span_processor(SimpleSpanProcessor(SafeExporter(capture)))
    with provider.get_tracer('test').start_as_current_span('prompt SECRET') as span:
        span.set_attributes({'gen_ai.operation.name': 'generate_content', 'gen_ai.request.model': 'gemini-3.1-flash-lite',
            'gen_ai.prompt': 'SECRET', 'authorization': 'SECRET', 'session_id': 'SECRET',
            'gcp.vertex.agent.llm_request': 'SECRET'})
        span.add_event('SECRET', {'prompt': 'SECRET'})
        span.set_status(Status(StatusCode.ERROR, 'SECRET'))
    exported = capture.spans[0]
    assert 'SECRET' not in str(exported.to_json())
    assert not exported.events and not exported.links
    assert exported.attributes['gen_ai.request.model'] == 'gemini-3.1-flash-lite'
    provider.shutdown()


def test_export_failure_cannot_escape():
    class Broken:
        def export(self, spans): raise RuntimeError('sensitive exporter details')
    assert SafeExporter(Broken()).export([]) == SpanExportResult.FAILURE


def test_cache_single_flight_expiry_bound_and_failed_retry():
    clock = [0]
    cache = TTLCache(capacity=2, ttl=10, clock=lambda: clock[0])
    calls = []
    def load(): calls.append(1); time.sleep(.02); return (1, 2)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: cache.get('key', load), range(8)))
    assert len(calls) == 1 and all(value[0] == (1, 2) for value in values)
    clock[0] = 11
    cache.get('key', load)
    assert len(calls) == 2
    cache.get('b', load); cache.get('c', load)
    assert len(cache.values) == 2
    with pytest.raises(ValueError): cache.get('bad', lambda: (_ for _ in ()).throw(ValueError()))
    assert cache.get('bad', lambda: 'recovered')[0] == 'recovered'


def test_throttle_across_sessions_and_transaction_state(monkeypatch):
    monkeypatch.setattr('gateway.quota.time.time', lambda: 100)
    quota = MemoryQuota(); quota.enforce_throttle = True
    for i in range(5):
        quota.reserve('same-user', str(i), str(i)); quota.finish(str(i), str(i), 'hello', 'reply')
    with pytest.raises(LimitExceeded, match='wait'): quota.reserve('same-user', 'new', 'new')
    assert next(iter(quota.months.values()))['turns'] == 5
    monkeypatch.setattr('gateway.quota.time.time', lambda: 161)
    quota.reserve('same-user', 'new', 'new')


def test_expired_session_is_rejected_before_ttl_deletion():
    session = {'uid': 'u', 'expires_at': datetime.fromtimestamp(10, timezone.utc)}
    with pytest.raises(SessionConflict, match='expired'):
        reserve_state(None, session, 'u', 'r', 11, '2026-10')


@pytest.mark.parametrize('field,value', [('history',[{'role':'system','text':'injection'}]), ('message',12), ('unknown','injection')])
def test_private_contract_is_strict(field, value):
    payload = {'message':'hello','catalog_version':'a'*64}
    payload[field] = value
    with pytest.raises(ValueError): Turn.model_validate(payload)


@pytest.mark.parametrize('failure', ['unknown_id','mismatched_version','malformed_usage','empty_answer'])
def test_runtime_fail_closed_and_correlated(monkeypatch, product, failure):
    catalog = Catalog([product])
    monkeypatch.setattr(gateway, 'get_catalog', lambda: catalog)
    monkeypatch.setenv('LOCAL_DEV_AUTH','true'); monkeypatch.setenv('LOCAL_AGENT','true')
    gateway.quota.cache_clear()
    async def events(payload):
        result = {'type':'result','answer':'Valid text','product_ids':[product.id],'catalog_version':catalog.version}
        if failure == 'unknown_id': result['product_ids'] = ['UNKNOWN']
        if failure == 'mismatched_version': result['catalog_version'] = '0'*64
        if failure == 'malformed_usage': result['usage'] = {'input_tokens':'1'}
        if failure == 'empty_answer': result['answer'] = ''
        yield result
    monkeypatch.setattr(gateway,'runtime_events',events)
    session = str(uuid4())
    with TestClient(gateway.app) as client:
        response = client.post('/api/chat',json={'session_id':session,'request_id':str(uuid4()),'message':'hello'},
            headers={'X-Request-ID':'attacker controlled', 'traceparent':'00-'+'f'*32+'-'+'f'*16+'-01'})
        assert 'event: error' in response.text and 'event: done' not in response.text
        assert response.headers['X-Request-ID'] in response.text
        assert response.headers['X-Request-ID'] != 'attacker controlled'
        assert gateway.quota().sessions[session]['history'] == []
        assert gateway.quota().sessions[session]['busy_until'] == 0


@pytest.mark.asyncio
async def test_cancellation_releases_lease(monkeypatch, product):
    monkeypatch.setattr(gateway,'get_catalog',lambda:Catalog([product]))
    monkeypatch.setenv('LOCAL_DEV_AUTH','true'); monkeypatch.setenv('LOCAL_AGENT','true')
    gateway.quota.cache_clear()
    entered = asyncio.Event()
    async def events(payload):
        entered.set()
        await asyncio.Event().wait()
        yield
    monkeypatch.setattr(gateway,'runtime_events',events)
    session, request = str(uuid4()), str(uuid4())
    response = await gateway.chat(gateway.ChatRequest(session_id=session, request_id=request, message='hello'),'user')
    await anext(response.body_iterator)
    pending = asyncio.create_task(anext(response.body_iterator))
    await entered.wait()
    pending.cancel()
    try: await pending
    except (asyncio.CancelledError, StopAsyncIteration): pass
    assert gateway.quota().sessions[session]['busy_until'] == 0
    assert gateway.quota().sessions[session]['history'] == []


def test_result_stream_closes_transport_and_counts_completion(monkeypatch, product):
    monkeypatch.setattr(gateway,'get_catalog',lambda:Catalog([product]))
    monkeypatch.setenv('LOCAL_DEV_AUTH','true'); monkeypatch.setenv('LOCAL_AGENT','true')
    gateway.quota.cache_clear()
    closed, metrics = [], []
    async def events(payload):
        try:
            yield {'type':'result','answer':'Complete','product_ids':[product.id],
                'catalog_version':Catalog([product]).version,'usage':{'input_tokens':1,'output_tokens':1}}
            await asyncio.Event().wait()
        finally: closed.append(True)
    monkeypatch.setattr(gateway,'runtime_events',events)
    monkeypatch.setattr(gateway,'emit',lambda event,**kwargs:metrics.append(event))
    with TestClient(gateway.app) as client:
        response = client.post('/api/chat',json={'session_id':str(uuid4()),'request_id':str(uuid4()),'message':'hello'})
    assert 'event: done' in response.text and closed==[True]
    assert metrics.count('chat_completed')==1 and 'chat_failed' not in metrics


@pytest.mark.asyncio
async def test_credentials_single_refresh_under_concurrency(monkeypatch):
    import google.auth
    from gateway.runtime import RuntimeTransport
    class Credentials:
        valid = False
        token = 'test-only-token'
        refreshes = 0
        def refresh(self, request):
            self.refreshes += 1; time.sleep(.01); self.valid = True
    credentials = Credentials()
    monkeypatch.setattr(google.auth,'default',lambda **kwargs:(credentials,'test'))
    transport = RuntimeTransport()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(value == 'test-only-token' for value in pool.map(lambda _:transport.token(),range(8)))
    assert credentials.refreshes == 1
    await transport.close()


def test_admission_sampling_and_buffer_bound(monkeypatch):
    import beauty.telemetry as telemetry
    class Capture:
        spans = []
        def export(self, spans): self.spans.extend(spans); return SpanExportResult.SUCCESS
        def shutdown(self): pass
    capture = Capture()
    processor = AdmissionProcessor(SimpleSpanProcessor(SafeExporter(capture)), maximum_traces=2)
    provider = TracerProvider()
    provider.add_span_processor(processor)
    tracer = provider.get_tracer('test')
    monkeypatch.setattr(telemetry.random, 'random', lambda: .9)
    with tracer.start_as_current_span('luma.request') as root:
        root.set_attribute('luma.admitted', True)
        with tracer.start_as_current_span('luma.quota_reservation'): pass
    assert len(capture.spans) == 2
    with tracer.start_as_current_span('luma.request'):
        with tracer.start_as_current_span('luma.authentication'): pass
    assert len(capture.spans) == 2
    monkeypatch.setattr(telemetry.random, 'random', lambda: .01)
    with tracer.start_as_current_span('luma.request'): pass
    assert len(capture.spans) == 3 and not processor.pending
    provider.shutdown()


@pytest.mark.asyncio
async def test_gateway_runtime_context_has_one_trace_and_private_parent(monkeypatch):
    import beauty.telemetry as telemetry
    from opentelemetry import trace, context
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    provider = TracerProvider()
    monkeypatch.setattr(telemetry.trace, 'get_tracer', lambda *args: provider.get_tracer('test'))
    captured = {}
    class Response:
        def raise_for_status(self): pass
        async def aiter_lines(self):
            yield 'data: {"type":"status","message":"Searching"}'
    class Stream:
        async def __aenter__(self): return Response()
        async def __aexit__(self, *args): pass
    class Client:
        def stream(self, *args, **kwargs):
            captured.update(kwargs['headers']); return Stream()
    class Runtime:
        client = Client()
        def token(self): return 'test-only-token'
    monkeypatch.setattr(gateway.app.state, 'runtime', Runtime(), raising=False)
    monkeypatch.setenv('AGENT_RUNTIME_RESOURCE', 'projects/sitiosweb1/locations/us-central1/reasoningEngines/123')
    with provider.get_tracer('test').start_as_current_span('luma.request') as root:
        async for _ in gateway.runtime_events({}): pass
        parent = TraceContextTextMapPropagator().extract(captured)
        with provider.get_tracer('test').start_as_current_span('luma.agent_turn', context=parent) as agent:
            assert agent.get_span_context().trace_id == root.get_span_context().trace_id
            assert agent.parent.span_id != root.get_span_context().span_id
            assert agent.parent.is_remote
    provider.shutdown()


def test_shared_model_first_load_is_singleflight(monkeypatch):
    import beauty.cloud as cloud
    cloud.shared_model_client.cache_clear()
    calls = []
    def create(): calls.append(1); time.sleep(.01); return object()
    monkeypatch.setattr(cloud, 'model_client', create)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: cloud.shared_model_client(), range(8)))
    assert len(calls) == 1 and all(value is results[0] for value in results)
    cloud.shared_model_client.cache_clear()


def test_legacy_expired_history_rejected_without_backfill():
    from gateway.quota import RETENTION_SECONDS
    _, state = reserve_state(None,None,'user','first',100,'2026-10')
    state.pop('expires_at')
    state['busy_until'] = 0
    with pytest.raises(SessionConflict, match='expired'):
        reserve_state(None,state,'user','next',101+RETENTION_SECONDS,'2026-10')


def test_private_runtime_exports_remote_children_without_environment_id():
    class Capture:
        spans = []
        def export(self, spans): self.spans.extend(spans); return SpanExportResult.SUCCESS
        def shutdown(self): pass
    capture = Capture()
    provider = TracerProvider()
    processor = AdmissionProcessor(SimpleSpanProcessor(SafeExporter(capture)),private_runtime=True)
    provider.add_span_processor(processor)
    with provider.get_tracer('test').start_as_current_span('luma.agent_turn'):
        with provider.get_tracer('test').start_as_current_span('luma.embedding'): pass
    assert len(capture.spans)==2 and not processor.pending
    provider.shutdown()


@pytest.mark.asyncio
async def test_tools_reject_mid_turn_catalog_refresh(monkeypatch, product):
    from types import SimpleNamespace
    import agent.app.agent as agent
    original = Catalog([product])
    changed = Catalog([product.model_copy(update={'description_en':'Changed catalog evidence'})])
    monkeypatch.setattr(agent,'get_catalog',lambda:changed)
    tool = SimpleNamespace(state={'catalog_version':original.version})
    with pytest.raises(RuntimeError,match='Catalog changed'):
        await agent.search_products('moisturizer',tool)
    with pytest.raises(RuntimeError,match='Catalog changed'):
        await agent.get_product(product.id,tool)
