import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from uuid import UUID

import httpx
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from beauty.catalog import get_catalog
from gateway.quota import FirestoreQuota, MemoryQuota, LimitExceeded, SessionConflict
from gateway.runtime import RuntimeTransport
from gateway.tracing import TraceMiddleware
from beauty.telemetry import span, emit, setup, shutdown, request_id, request_started
from opentelemetry import trace
from beauty.contracts import Result
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace import Status, StatusCode


async def threaded(operation, function, *args, **kwargs):
    with span(operation):
        return await asyncio.to_thread(function, *args, **kwargs)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.propagate = False


def firebase_app():
    import firebase_admin
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(options={'projectId': 'sitiosweb1'})


async def visitor(authorization: str | None = Header(default=None)):
    if os.getenv('LOCAL_DEV_AUTH') == 'true':
        if os.getenv('ENVIRONMENT') == 'production' or os.getenv('K_SERVICE'):
            raise HTTPException(503, 'Unsafe auth configuration')
        return 'local-development-visitor'
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Sign in anonymously to start a conversation')
    from firebase_admin import auth
    try:
        claims = await threaded('authentication', auth.verify_id_token, authorization[7:], app=firebase_app())
        return claims['uid']
    except Exception:
        raise HTTPException(401, 'Invalid or expired session') from None


@lru_cache
def quota():
    if os.getenv('LOCAL_DEV_AUTH') == 'true' and not os.getenv('K_SERVICE') and os.getenv('ENVIRONMENT') != 'production':
        return MemoryQuota()
    from firebase_admin import firestore
    return FirestoreQuota(firestore.client(app=firebase_app()))


@asynccontextmanager
async def lifespan(app):
    setup('luma-gateway')
    await threaded('catalog_load', get_catalog)
    if os.getenv('ENVIRONMENT') == 'production':
        if os.getenv('LOCAL_DEV_AUTH') == 'true' or not os.getenv('AGENT_RUNTIME_RESOURCE'):
            raise RuntimeError('Production requires Firebase auth and an Agent Runtime resource')
        quota()
    app.state.runtime = RuntimeTransport()
    try:
        yield
    finally:
        await app.state.runtime.close()
        shutdown()


app = FastAPI(title='Luma Beauty API', lifespan=lifespan,
    docs_url=None if os.getenv('ENVIRONMENT') == 'production' else '/docs',
    redoc_url=None if os.getenv('ENVIRONMENT') == 'production' else '/redoc',
    openapi_url=None if os.getenv('ENVIRONMENT') == 'production' else '/openapi.json')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','), allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'], expose_headers=['X-Request-ID'])
app.add_middleware(TraceMiddleware)


class ChatRequest(BaseModel):
    session_id: UUID
    request_id: UUID
    message: str = Field(min_length=1, max_length=1200)

    @property
    def clean_message(self):
        value = self.message.strip()
        if not value:
            raise HTTPException(422, 'Enter a message')
        return value


def sse(kind, data):
    return f'event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


@app.get('/health')
def health():
    return {'status': 'ok', 'catalog_count': len(get_catalog().products), 'catalog_version': get_catalog().version,
            'agent_configured': bool(os.getenv('AGENT_RUNTIME_RESOURCE') or os.getenv('LOCAL_AGENT') == 'true')}


@app.get('/api/products')
def products(q: str = '', category: str | None = None, max_price: float | None = None):
    if len(q) > 200 or (max_price is not None and (max_price < 0 or max_price > 100000)):
        raise HTTPException(422, 'Invalid filters')
    catalog = get_catalog()
    rows = catalog.search(q, max_price_usd=max_price, category=category, limit=100)
    return {'products': [p.public() for p in rows], 'total': len(catalog.products), 'version': catalog.version,
            'categories': sorted({p.category for p in catalog.products.values()})}


@app.get('/api/products/{product_id}')
def detail(product_id: str):
    product = get_catalog().products.get(product_id)
    if not product:
        raise HTTPException(404, 'Product not found')
    return product.public()


async def runtime_events(payload):
    resource = os.getenv('AGENT_RUNTIME_RESOURCE')
    if not resource:
        if os.getenv('LOCAL_AGENT') != 'true':
            raise RuntimeError('Shopping agent is not configured')
        from agent.app.shopping import respond
        async for event in respond(payload):
            yield event
        return
    import re
    if not re.fullmatch(r'projects/sitiosweb1/locations/us-central1/reasoningEngines/\d+', resource):
        raise RuntimeError('Unexpected Agent Runtime resource')
    token = await asyncio.to_thread(app.state.runtime.token)
    headers = {'Authorization': f'Bearer {token}'}
    url = f'https://us-central1-aiplatform.googleapis.com/reasoningEngines/v1/{resource}/api/shop/stream'
    with span('runtime_transport'):
        TraceContextTextMapPropagator().inject(headers)
        async with app.state.runtime.client.stream('POST', url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    yield json.loads(line[6:])


@app.post('/api/chat')
async def chat(request: ChatRequest, uid: str = Depends(visitor)):
    started = request_started.get() or time.monotonic()
    rid = request_id.get()
    message = request.clean_message
    catalog = await threaded('catalog_load', get_catalog)
    if not catalog.products:
        raise HTTPException(503, 'The real product catalog is awaiting import. Shopping advice will be available after it is loaded.')
    if not os.getenv('AGENT_RUNTIME_RESOURCE') and os.getenv('LOCAL_AGENT') != 'true':
        raise HTTPException(503, 'Shopping agent is awaiting configuration')
    try:
        history, turns = await threaded('quota_reservation', quota().reserve, uid, str(request.session_id), str(request.request_id))
    except LimitExceeded as exc:
        emit('chat_rejected', outcome='quota')
        raise HTTPException(429, str(exc)) from None
    except SessionConflict as exc:
        emit('chat_rejected', outcome='conflict')
        raise HTTPException(409, str(exc)) from None
    except Exception as exc:
        emit('chat_failed', outcome='internal', duration_seconds=time.monotonic()-started,
            error_type=type(exc).__name__)
        raise HTTPException(503, 'Chat allowance could not be verified') from None
    trace.get_current_span().set_attribute('luma.admitted', True)

    async def stream():
        answer = None
        completed = False
        runtime = runtime_events({'message': message, 'history': history, 'catalog_version': catalog.version})
        try:
            emit('chat_started')
            emit('first_status', first_status_seconds=time.monotonic()-started)
            yield sse('status', {'message': 'Checking the product catalog…'})
            async with asyncio.timeout(90):
                async for event in runtime:
                    if completed:
                        raise RuntimeError('Runtime sent events after final result')
                    if event.get('type') == 'status':
                        yield sse('status', {'message': event['message']})
                    elif event.get('type') == 'error':
                        raise RuntimeError('Agent could not validate its response')
                    elif event.get('type') == 'result':
                        with span('response_validation'):
                            result = Result.model_validate(event)
                            current = await threaded('catalog_load', get_catalog)
                            if result.catalog_version != current.version or any(pid not in catalog.products for pid in result.product_ids):
                                emit('guard_failure', outcome='invalid_result')
                                raise RuntimeError('Invalid grounded response')
                            candidate_answer = result.answer
                            ids = list(dict.fromkeys(result.product_ids))
                            cards = [catalog.products[pid].public() for pid in ids]
                        # Cards always come from canonical data, never model-supplied prices or links.
                        usage = result.usage.model_dump()
                        # Commit history and release the session before the client can send its next turn.
                        await threaded('history_persistence', quota().finish, str(request.session_id), str(request.request_id), message, candidate_answer, ids)
                        answer = candidate_answer
                        completed = True
                        yield sse('answer', {'text': answer})
                        yield sse('recommendations', {'products': cards})
                        yield sse('done', {'turns_remaining': 10 - turns, 'usage': usage})
                        emit('chat_completed', outcome='ok', duration_seconds=time.monotonic()-started, **usage,
                            model_calls=result.model_calls, tool_calls=result.tool_calls,
                            model_cost_usd=usage['input_tokens']*.25/1e6 + usage['output_tokens']*1.5/1e6)
                        break
                    else:
                        raise RuntimeError('Unexpected runtime event')
                if not completed:
                    raise RuntimeError('Agent stream ended without a validated result')
        except (Exception, asyncio.CancelledError) as exc:
            emit('chat_failed', outcome='cancelled' if isinstance(exc, asyncio.CancelledError) else 'internal',
                duration_seconds=time.monotonic()-started, error_type=type(exc).__name__)
            if not isinstance(exc, asyncio.CancelledError):
                yield sse('error', {'message': 'The assistant could not finish. Please try again. This attempt counts toward the demo allowance.', 'turns_remaining': 10 - turns, 'request_id': rid})
        finally:
            # Close on the same task/context that entered the transport span.
            # Do not leave the HTTP stream waiting on garbage collection.
            try:
                await runtime.aclose()
            except Exception as exc:
                emit('runtime_cleanup', outcome='failed', error_type=type(exc).__name__)
            if not completed:
                try:
                    await asyncio.shield(threaded('lease_release', quota().finish, str(request.session_id), str(request.request_id), message, None))
                except Exception as exc:
                    # Lease expires automatically if persistence is unavailable.
                    emit('lease_cleanup', outcome='failed', error_type=type(exc).__name__)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
