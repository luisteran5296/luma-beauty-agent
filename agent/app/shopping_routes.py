import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.shopping import respond
from beauty.contracts import Turn
from opentelemetry import context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

router = APIRouter()


@router.post('/shop/stream')
async def stream(turn: Turn, request: Request):
    # Private runtime route. Only gateway SA receives IAM access.
    async def events():
        parent = TraceContextTextMapPropagator().extract({'traceparent': request.headers.get('traceparent', '')})
        token = context.attach(parent)
        try:
            async for event in respond(turn.model_dump()):
                yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
        except Exception:
            yield 'data: {"type":"error"}\n\n'
        finally:
            context.detach(token)
    return StreamingResponse(events(), media_type='text/event-stream')
