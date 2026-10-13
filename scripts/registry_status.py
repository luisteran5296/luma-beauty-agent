"""Read-only native discovery. Never create a duplicate or change runtime IAM."""
import json
from pathlib import Path
from google.auth.transport.requests import AuthorizedSession
from beauty.cloud import GcloudCredentials


def main():
    resource = json.loads(Path('agent/deployment_metadata.json').read_text())['remote_agent_runtime_id']
    engine = resource.rsplit('/', 1)[-1]
    session = AuthorizedSession(GcloudCredentials.create())
    session.headers['x-goog-user-project'] = 'sitiosweb1'
    matches = []
    for region in ['global', 'us-central1']:
        url = f'https://agentregistry.googleapis.com/v1/projects/sitiosweb1/locations/{region}/agents'
        token = None
        while True:
            response = session.get(url, params={'pageToken': token} if token else {}, timeout=30)
            if response.status_code != 200:
                raise SystemExit(f'Registry inspection failed (HTTP {response.status_code}); registration blocked')
            result = response.json()
            matches.extend(item for item in result.get('agents', []) if engine in json.dumps(item))
            token = result.get('nextPageToken')
            if not token: break
    report = {'runtime_resource': resource, 'discovered': matches, 'registration_required': not matches}
    Path('reports').mkdir(exist_ok=True)
    Path('reports/registry-status.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'matches': len(matches), 'registration_required': not matches}))


if __name__ == '__main__': main()
