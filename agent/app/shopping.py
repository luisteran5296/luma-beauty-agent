"""Bounded, stateless turn runner; gateway owns authenticated conversation history."""
import json
import time
from uuid import uuid4
from pydantic import BaseModel, Field
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig
from google.genai import types
from beauty.catalog import get_catalog


class Reply(BaseModel):
    answer: str = Field(min_length=1, max_length=6000)
    product_ids: list[str] = Field(max_length=3)


async def respond(payload):
    from .agent import app as agent_app, evidence
    catalog = get_catalog()
    if not catalog.products:
        raise RuntimeError('Catalog is empty')
    if payload.get('catalog_version') != catalog.version:
        raise RuntimeError('Catalog version mismatch')
    started = time.monotonic()
    sessions = InMemorySessionService()
    session_id, user_id = uuid4().hex, uuid4().hex
    latest_ids = next((x.get('product_ids', []) for x in reversed(payload.get('history', [])) if x.get('role') == 'assistant'), [])[:3]
    prior_products = [catalog.products[pid] for pid in latest_ids if pid in catalog.products]
    await sessions.create_session(app_name=agent_app.name, user_id=user_id, session_id=session_id,
        state={'allowed_product_ids': [p.id for p in prior_products]})
    runner = Runner(app=agent_app, session_service=sessions)
    history = [{'role': x['role'], 'text': str(x['text'])[:1400]} for x in payload.get('history', [])[-12:]]
    content = json.dumps({'prior_transcript': history, 'prior_products_current_catalog': [evidence(p) for p in prior_products],
        'shopper_message': str(payload['message'])[:1200]}, ensure_ascii=False)
    final_text = ''
    yield {'type': 'status', 'message': 'Finding products that fit your needs…'}
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id,
            new_message=types.Content(role='user', parts=[types.Part(text=content)]), run_config=RunConfig(max_llm_calls=3)):
            if event.is_final_response() and event.content:
                final_text = ''.join(part.text or '' for part in event.content.parts or [] if not part.thought)
        reply = Reply.model_validate_json(final_text)
        state = (await sessions.get_session(app_name=agent_app.name, user_id=user_id, session_id=session_id)).state
        allowed = set(state.get('allowed_product_ids', []))
        if any(pid not in allowed or pid not in catalog.products for pid in reply.product_ids):
            raise RuntimeError('Model recommended an ungrounded product ID')
        yield {'type': 'result', 'answer': reply.answer, 'product_ids': list(dict.fromkeys(reply.product_ids)),
               'catalog_version': catalog.version, 'usage': state.get('usage', {}), 'latency_seconds': round(time.monotonic() - started, 3)}
    finally:
        await sessions.delete_session(app_name=agent_app.name, user_id=user_id, session_id=session_id)
