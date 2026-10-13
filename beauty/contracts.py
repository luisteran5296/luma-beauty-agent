"""Strict, shared private-runtime wire contract."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HistoryItem(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    role: Literal['user', 'assistant']
    text: str = Field(max_length=6000)
    product_ids: list[str] = Field(default_factory=list, max_length=3)


class Turn(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    message: str = Field(min_length=1, max_length=1200)
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)
    catalog_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    traceparent: str | None = Field(default=None,max_length=55,
        pattern=r'^00-[a-f0-9]{32}-[a-f0-9]{16}-(00|01)$')

    @field_validator('traceparent')
    @classmethod
    def nonzero_trace(cls,value):
        if value and (value.split('-')[1]=='0'*32 or value.split('-')[2]=='0'*16):
            raise ValueError('Trace identifiers must be nonzero')
        return value


class Usage(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class Result(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    type: Literal['result']
    answer: str = Field(min_length=1, max_length=6000)
    product_ids: list[str] = Field(max_length=3)
    catalog_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    usage: Usage = Field(default_factory=Usage)
    latency_seconds: float = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0, le=3)
    tool_calls: int = Field(default=0, ge=0, le=4)
