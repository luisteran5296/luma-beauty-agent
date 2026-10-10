import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.shopping import respond

router = APIRouter()


class HistoryItem(BaseModel):
    role: str = Field(pattern='^(user|assistant)$')
    text: str = Field(max_length=6000)
    product_ids: list[str] = Field(default_factory=list, max_length=3)


class Turn(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)
    catalog_version: str = Field(pattern=r'^[a-f0-9]{64}$')


@router.post('/shop/stream')
async def stream(turn: Turn):
    # Private runtime route. Only gateway SA receives IAM access.
    async def events():
        try:
            async for event in respond(turn.model_dump()):
                yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
        except Exception:
            yield 'data: {"type":"error"}\n\n'
    return StreamingResponse(events(), media_type='text/event-stream')
