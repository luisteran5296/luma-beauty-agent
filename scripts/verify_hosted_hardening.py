"""Explicit bounded hosted validation; uses a new synthetic visitor/session only.

--exercise-failures corrupts only this tool's synthetic session history, restores
it in finally, and consumes three admitted failure attempts under normal quotas.
Tokens and visitor/session identifiers are never written to the report.
"""
import argparse
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import requests
from google.cloud import firestore
from google.auth.transport.requests import AuthorizedSession
from beauty.cloud import credentials
from gateway.quota import month_key

BASE = 'https://beauty-store-api-cgbi4c4u5q-uc.a.run.app'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exercise-failures',action='store_true')
    parser.add_argument('--exercise-cancellation',action='store_true')
    args = parser.parse_args()
    db = firestore.Client(project='sitiosweb1',credentials=credentials())
    before = db.collection('beauty_store_quotas').document(month_key()).get().to_dict() or {}
    if before.get('turns',0)>980 or before.get('conversations',0)>=99:
        raise SystemExit('Insufficient real allowance for bounded validation')
    http = requests.Session()
    health = http.get(BASE+'/health',timeout=60)
    health.raise_for_status()
    assert health.json()['catalog_count']==100
    assert health.headers.get('X-Request-ID')
    assert http.get(BASE+'/openapi.json',timeout=30).status_code==404
    key = json.loads(Path('reports/firebase-web-config.json').read_text())['apiKey']
    signup = http.post('https://identitytoolkit.googleapis.com/v1/accounts:signUp',params={'key':key},
        json={'returnSecureToken':True},timeout=30)
    signup.raise_for_status()
    identity = signup.json()
    token, uid = identity['idToken'], identity['localId']
    session = str(uuid4())
    headers = {'Authorization':'Bearer '+token,'Origin':'https://sitiosweb1-luma-beauty.web.app'}
    turns = []
    def turn():
        started = time.monotonic()
        kinds, data, first = [], [], None
        with http.post(BASE+'/api/chat',headers=headers,stream=True,timeout=100,
                json={'session_id':session,'request_id':str(uuid4()),'message':'Find a moisturizer for dry skin under $15.'}) as response:
            assert response.status_code==200
            rid = response.headers['X-Request-ID']
            for line in response.iter_lines(decode_unicode=True,chunk_size=1):
                if line.startswith('event: '):
                    kinds.append(line[7:])
                    if first is None: first=time.monotonic()-started
                if line.startswith('data: '): data.append(json.loads(line[6:]))
        result = {'request_id':rid,'events':kinds,'first_status_seconds':first,
                  'completion_seconds':time.monotonic()-started,'http_status':200}
        turns.append(result)
        return result,data
    first,data = turn()
    assert 'done' in first['events'] and 'error' not in first['events']
    ref = db.collection('beauty_store_sessions').document(hashlib.sha256(session.encode()).hexdigest())
    own = ref.get().to_dict()
    assert own['uid']==uid and own['busy_until']==0 and own.get('expires_at')
    if args.exercise_failures:
        original = own['history']
        try:
            ref.update({'history':[{'role':'invalid-synthetic-role','text':'synthetic validation fault'}]})
            for _ in range(3):
                result,events = turn()
                assert 'error' in result['events'] and 'done' not in result['events']
                error = next(item for item in events if 'request_id' in item)
                assert error['request_id']==result['request_id']
                assert ref.get().to_dict()['busy_until']==0
        finally:
            ref.update({'history':original})
    cancelled_rid = None
    if args.exercise_cancellation:
        with http.post(BASE+'/api/chat',headers=headers,stream=True,timeout=100,
                json={'session_id':session,'request_id':str(uuid4()),
                    'message':'Compare moisturizers under $15.'}) as response:
            response.raise_for_status()
            cancelled_rid=response.headers['X-Request-ID']
            for line in response.iter_lines(decode_unicode=True,chunk_size=1):
                if line.startswith('event: status'):
                    break  # Close only this synthetic visitor's connection.
        for _ in range(15):
            if ref.get().to_dict()['busy_until']==0: break
            time.sleep(2)
        assert ref.get().to_dict()['busy_until']==0
    cloud = AuthorizedSession(credentials())
    cloud.headers['x-goog-user-project']='sitiosweb1'
    observed = []
    trace = None
    for _ in range(12):
        # Public health traffic also lets request-based instances drain exporters.
        http.get(BASE+'/health',timeout=30)
        cloud.get('https://us-central1-aiplatform.googleapis.com/reasoningEngines/v1/'
            'projects/719793696278/locations/us-central1/reasoningEngines/4860633318019825664/api/health',timeout=30)
        response = cloud.post('https://logging.googleapis.com/v2/entries:list',timeout=30,json={
            'resourceNames':['projects/sitiosweb1'],'filter':
                'timestamp >= "'+(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()+
                '" AND jsonPayload.request_id="'+first['request_id']+'"',
                'orderBy':'timestamp desc','pageSize':100})
        response.raise_for_status()
        observed = response.json().get('entries',[])
        trace_name = next((e.get('trace') for e in observed if e.get('trace')),None)
        if trace_name:
            found = cloud.get('https://cloudtrace.googleapis.com/v1/'+trace_name,timeout=30)
            if found.status_code==200:
                spans=found.json().get('spans',[])
                names = {s['name'] for s in spans}
                ids={s['spanId'] for s in spans}
                roots=[s for s in spans if s.get('parentSpanId','0')=='0']
                connected=all(s.get('parentSpanId','0')=='0' or s['parentSpanId'] in ids for s in spans)
                if ({'luma.request','luma.agent_turn','adk.generate_content','adk.execute_tool'} <= names
                        and len(roots)==1 and roots[0]['name']=='luma.request' and connected):
                    trace=found.json(); break
        time.sleep(5)
    serialized = json.dumps({'logs':observed,'trace':trace})
    assert token not in serialized and uid not in serialized and session not in serialized
    assert 'Find a moisturizer for dry skin under $15.' not in serialized
    assert 'invalid-synthetic-role' not in serialized
    cancellation_outcome=None
    if cancelled_rid:
        result=cloud.post('https://logging.googleapis.com/v2/entries:list',timeout=30,json={
            'resourceNames':['projects/sitiosweb1'],'filter':
                'jsonPayload.request_id="'+cancelled_rid+'" AND jsonPayload.event="chat_failed"',
            'orderBy':'timestamp desc','pageSize':10})
        result.raise_for_status()
        cancellation_outcome=next((e['jsonPayload'].get('outcome') for e in result.json().get('entries',[])),None)
    report = {'synthetic_only':True,'turns':turns,'quota_before':before,
        'trace':trace,'correlated_log_events':[e.get('jsonPayload',{}).get('event') for e in observed],
        'trace_found':bool(trace),'sensitive_content_excluded':True,
        'controlled_failures_verified':args.exercise_failures,'lease_cleanup_verified':True,
        'hosted_disconnect_lease_verified':args.exercise_cancellation,
        'disconnect_request_id':cancelled_rid,
        'cancellation_outcome':cancellation_outcome}
    Path('reports/hosted-hardening.json').write_text(json.dumps(report,indent=2,default=str))
    print(json.dumps({k:v for k,v in report.items() if k not in ['trace','quota_before']}))
    if not trace: raise SystemExit('Trace not available yet; inspect ingestion before acceptance')


if __name__ == '__main__': main()
