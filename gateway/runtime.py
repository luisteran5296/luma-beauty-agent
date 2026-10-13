"""Lifecycle-managed transport and refresh-safe keyless credentials."""
import asyncio
import threading
import httpx
from beauty.telemetry import span


class RuntimeTransport:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=90, limits=httpx.Limits(max_connections=16, max_keepalive_connections=8))
        self.credentials = None
        self.lock = threading.Lock()

    def token(self):
        import google.auth
        from google.auth.transport.requests import Request
        with self.lock, span('credentials'):
            if self.credentials is None:
                self.credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            if not self.credentials.valid:
                self.credentials.refresh(Request())
            return self.credentials.token

    async def close(self):
        await self.client.aclose()
