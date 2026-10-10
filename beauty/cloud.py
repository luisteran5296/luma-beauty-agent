import os
import subprocess
from google import genai


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
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                self.token = result.stdout.strip()
                self.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=50)

        selected = SelectedAccountCredentials()
        selected.refresh(None)
        return selected


def credentials():
    # Explicit opt-in for local CLI credentials. Tokens are captured, never printed or written.
    if os.getenv('USE_GCLOUD_CREDENTIALS') == 'true':
        return GcloudCredentials.create()
    return None


def model_client():
    return genai.Client(vertexai=True, project='sitiosweb1', location='global', credentials=credentials())


def embed(query, task='RETRIEVAL_QUERY'):
    from google.genai import types
    with model_client() as client:
        result = client.models.embed_content(model='gemini-embedding-001', contents=query,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=768))
    return result.embeddings[0].values
