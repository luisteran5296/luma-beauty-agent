from uuid import uuid4
from fastapi.testclient import TestClient
from beauty.catalog import Catalog
import gateway.main as gateway


def test_empty_catalog_and_auth(monkeypatch):
    monkeypatch.setattr(gateway, 'get_catalog', lambda: Catalog([]))
    monkeypatch.delenv('LOCAL_DEV_AUTH',raising=False)
    with TestClient(gateway.app) as client:
        assert client.get('/api/products').json()['products'] == []
        payload = {'session_id':str(uuid4()),'request_id':str(uuid4()),'message':'hello'}
        assert client.post('/api/chat',json=payload).status_code == 401
        monkeypatch.setenv('LOCAL_DEV_AUTH','true')
        assert client.post('/api/chat',json=payload).status_code == 503


def test_streamed_cards_are_canonical(monkeypatch, product):
    catalog = Catalog([product])
    monkeypatch.setattr(gateway,'get_catalog',lambda:catalog)
    monkeypatch.setenv('LOCAL_DEV_AUTH','true')
    monkeypatch.setenv('LOCAL_AGENT','true')
    gateway.quota.cache_clear()
    async def events(payload):
        assert payload['catalog_version'] == catalog.version
        yield {'type':'result','answer':'Fixture response','product_ids':[product.id], 'catalog_version':catalog.version,'usage':{'input_tokens':1,'output_tokens':1}}
    monkeypatch.setattr(gateway,'runtime_events',events)
    with TestClient(gateway.app) as client:
        response = client.post('/api/chat',json={'session_id':str(uuid4()),'request_id':str(uuid4()),'message':'moisturizer'})
        assert response.status_code == 200
        assert 'event: done' in response.text
        assert 'INVALID-ID' not in response.text
        assert '"price_usd": 10.0' in response.text
        assert client.get('/api/products/nonexistent').status_code == 404


def test_runtime_failure_releases_session(monkeypatch, product):
    monkeypatch.setattr(gateway,'get_catalog',lambda:Catalog([product]))
    monkeypatch.setenv('LOCAL_DEV_AUTH','true')
    monkeypatch.setenv('LOCAL_AGENT','true')
    gateway.quota.cache_clear()
    async def events(payload):
        raise RuntimeError('private backend details')
        yield
    monkeypatch.setattr(gateway,'runtime_events',events)
    session = str(uuid4())
    with TestClient(gateway.app) as client:
        response = client.post('/api/chat',json={'session_id':session,'request_id':str(uuid4()),'message':'moisturizer'})
        assert 'event: error' in response.text
        assert 'private backend details' not in response.text
        assert gateway.quota().sessions[session]['busy_until'] == 0


def test_production_rejects_development_auth(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT','production')
    monkeypatch.setenv('LOCAL_DEV_AUTH','true')
    monkeypatch.setattr(gateway,'get_catalog',lambda:Catalog([]))
    import pytest
    with pytest.raises(RuntimeError, match='Production requires'):
        with TestClient(gateway.app):
            pass


def test_truncated_runtime_stream_returns_error(monkeypatch, product):
    monkeypatch.setattr(gateway,'get_catalog',lambda:Catalog([product]))
    monkeypatch.setenv('LOCAL_DEV_AUTH','true')
    monkeypatch.setenv('LOCAL_AGENT','true')
    gateway.quota.cache_clear()
    async def events(payload):
        yield {'type':'status','message':'Searching'}
    monkeypatch.setattr(gateway,'runtime_events',events)
    session = str(uuid4())
    with TestClient(gateway.app) as client:
        response = client.post('/api/chat',json={'session_id':session,'request_id':str(uuid4()),'message':'moisturizer'})
        assert 'event: error' in response.text and 'event: done' not in response.text
        assert gateway.quota().sessions[session]['busy_until'] == 0
        assert gateway.quota().sessions[session]['history'] == []
