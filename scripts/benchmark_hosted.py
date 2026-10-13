"""Bounded hosted performance cases using synthetic anonymous visitors only."""
import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import requests
from scripts.evaluate_shopping import SCENARIOS
from google.cloud import firestore
from beauty.cloud import credentials
from gateway.quota import month_key

BASE='https://beauty-store-api-cgbi4c4u5q-uc.a.run.app'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--concurrency',type=int,choices=[1,2],default=1)
    args=parser.parse_args()
    quota=firestore.Client(project='sitiosweb1',credentials=credentials()).collection(
        'beauty_store_quotas').document(month_key()).get().to_dict() or {}
    if quota.get('turns',0)>990 or quota.get('conversations',0)>94:
        raise SystemExit('Insufficient real allowance for bounded benchmark')
    key=json.loads(Path('reports/firebase-web-config.json').read_text())['apiKey']
    def scenario(pair):
        index,messages=pair
        http=requests.Session()
        signup=http.post('https://identitytoolkit.googleapis.com/v1/accounts:signUp',params={'key':key},
            json={'returnSecureToken':True},timeout=30)
        signup.raise_for_status()
        token=signup.json()['idToken']
        headers={'Authorization':'Bearer '+token,'Origin':'https://sitiosweb1-luma-beauty.web.app'}
        session=str(uuid4())
        rows=[]
        try:
            for prompt in messages:
                started=time.monotonic()
                first=None
                kinds=[]
                data=[]
                with http.post(BASE+'/api/chat',headers=headers,stream=True,timeout=100,json={
                    'session_id':session,'request_id':str(uuid4()),'message':prompt}) as response:
                    response.raise_for_status()
                    rid=response.headers['X-Request-ID']
                    for line in response.iter_lines(decode_unicode=True,chunk_size=1):
                        if line.startswith('event: '):
                            kinds.append(line[7:])
                            if first is None:first=time.monotonic()-started
                        if line.startswith('data: '):data.append(json.loads(line[6:]))
                rows.append({'case':index,'request_id':rid,'first_status_seconds':first,
                    'completion_seconds':time.monotonic()-started,'passed':'done' in kinds and 'error' not in kinds,
                    'usage':next((d['usage'] for d in data if 'usage' in d),{})})
        finally:
            # Delete this tool's own ephemeral Firebase identity; normal Firestore
            # history retention and global counters remain unchanged.
            http.post('https://identitytoolkit.googleapis.com/v1/accounts:delete',params={'key':key},
                json={'idToken':token},timeout=30)
            http.close()
        return rows
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        rows=[row for group in pool.map(scenario,enumerate(SCENARIOS)) for row in group]
    durations=sorted(r['completion_seconds'] for r in rows)
    report={'synthetic_only':True,'concurrency':args.concurrency,'turns':rows,
        'p50_seconds':durations[math.ceil(len(rows)*.5)-1],
        'p95_seconds':durations[math.ceil(len(rows)*.95)-1],
        'cloud_cold_start_isolated':False,'all_completed':all(r['passed'] for r in rows)}
    Path(f'reports/hosted-benchmark-c{args.concurrency}.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='turns'}))
    if not report['all_completed']:raise SystemExit('Hosted benchmark has failed streams')


if __name__=='__main__':main()
