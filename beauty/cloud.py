import os
import subprocess
import threading
from functools import lru_cache
from google import genai
from beauty.cache import TTLCache
from beauty.telemetry import span, emit

_queries = TTLCache()
_client_lock = threading.RLock()


class GcloudCredentials:
    @staticmethod
    def create():
        from google.auth.credentials import Credentials
        from datetime import datetime, timedelta, timezone

        class SelectedAccountCredentials(Credentials):
            def refresh(self, request):
                command = ['gcloud.cmd' if os.name == 'nt' else 'gcloud', 'auth', 'print-access-token']
                if os.getenv('GCLOUD_ACCOUNT'):
                    command.append('--account=' + os.environ['GCLOUD_ACCOUNT'])
                with span('credentials'):
                    result = subprocess.run(command, capture_output=True, text=True, check=True)
                self.token = result.stdout.strip()
                self.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=50)

        selected = SelectedAccountCredentials()
        selected.refresh(None)
        return selected


@lru_cache(maxsize=1)
def credentials():
    # Explicit opt-in for local CLI credentials. Tokens are captured, never printed or written.
    if os.getenv('USE_GCLOUD_CREDENTIALS') == 'true':
        return GcloudCredentials.create()
    return None


def model_client():
    return genai.Client(vertexai=True, project='sitiosweb1', location='global', credentials=credentials())


@lru_cache(maxsize=1)
def _shared_model_client():
    return model_client()


def shared_model_client():
    # lru_cache alone permits duplicate concurrent first-load calls.
    with _client_lock:
        return _shared_model_client()


shared_model_client.cache_info = _shared_model_client.cache_info
shared_model_client.cache_clear = _shared_model_client.cache_clear


def embed(query, task='RETRIEVAL_QUERY'):
    from google.genai import types
    def load():
        result = shared_model_client().models.embed_content(model='gemini-embedding-001', contents=query,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=768))
        return tuple(result.embeddings[0].values)
    with span('embedding'):
        if task == 'RETRIEVAL_QUERY':
            # No answer cache; query text exists only in bounded process memory.
            key = ('gemini-embedding-001', 768, task, ' '.join(query.split()))
            value, hit = _queries.get(key, load)
            emit('embedding_cache', cache_hit=hit)
            return list(value)
        return list(load())
