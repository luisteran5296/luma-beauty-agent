"""Synthetic private adapter compatibility check; no user content or tokens printed."""
import json
from pathlib import Path
from google.auth.transport.requests import AuthorizedSession
from beauty.cloud import credentials
from uuid import uuid4


def main():
    cloud=AuthorizedSession(credentials())
    base='https://us-central1-aiplatform.googleapis.com/reasoningEngines/v1/projects/719793696278/locations/us-central1/reasoningEngines/4860633318019825664/api'
    health=cloud.get(base+'/health',timeout=60)
    print('health',health.status_code,health.text[:500])
    payload={'message':'Hello','history':[],'catalog_version':'c11ba6e461c161c0d3db440b7e0a1deac79ef1f969245612a51e67253ac2861c',
        'traceparent':f'00-{uuid4().hex}-{uuid4().hex[:16]}-03'}
    response=cloud.post(base+'/shop/stream',json=payload,timeout=100)
    print('status',response.status_code)
    if response.status_code!=200:
        # Body contains only this synthetic request's validation diagnostics.
        print(response.text[:2000])
    Path('reports/runtime-probe.json').write_text(json.dumps({'status':response.status_code}))
    if response.status_code!=200 or '"type": "error"' in response.text:
        raise SystemExit('Private runtime compatibility probe failed')


if __name__=='__main__':main()
