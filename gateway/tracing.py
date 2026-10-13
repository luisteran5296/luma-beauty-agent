"""ASGI instrumentation spans the full SSE lifetime; public headers cannot parent traces."""
import time
from uuid import uuid4
from opentelemetry import context
from beauty.telemetry import span, request_id, request_started


class TraceMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        rid = uuid4().hex
        support = request_id.set(rid)
        started = request_started.set(time.monotonic())
        root = context.attach(context.Context())
        async def response(message):
            if message['type'] == 'http.response.start':
                message.setdefault('headers', []).append((b'x-request-id', rid.encode()))
            await send(message)
        try:
            # The bounded processor decides after quota admission. Public trace
            # headers cannot force recording or influence the sampling decision.
            with span('request'):
                await self.app(scope, receive, response)
        finally:
            context.detach(root)
            request_id.reset(support)
            request_started.reset(started)
