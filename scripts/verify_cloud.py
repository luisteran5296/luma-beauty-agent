"""Production smoke checks; credentials and visitor tokens never leave memory."""
import json
from pathlib import Path
from uuid import uuid4
import requests
from scripts.deploy_cloud import ROOT

API = 'https://beauty-store-api-cgbi4c4u5q-uc.a.run.app'

def main():
    health = requests.get(API+'/health', timeout=60)
    health.raise_for_status()
    assert health.json()['catalog_count'] == 100
    products = requests.get(API+'/api/products', timeout=60).json()['products']
    assert len(products) == 100
    ids = {p['id'] for p in products}
    payload = {'session_id':str(uuid4()), 'request_id':str(uuid4()), 'message':'Find a moisturizer under $20.'}
    assert requests.post(API+'/api/chat',json=payload,timeout=30).status_code == 401
    config = json.loads((ROOT/'reports/firebase-web-config.json').read_text())
    auth = requests.post('https://identitytoolkit.googleapis.com/v1/accounts:signUp',
                         params={'key':config['apiKey']},json={'returnSecureToken':True},timeout=30)
    auth.raise_for_status()
    token = auth.json()['idToken']
    headers = {'Authorization':'Bearer '+token,'Origin':'https://sitiosweb1-luma-beauty.web.app'}
    # Browser visitors must not read quota/session records directly.
    direct = requests.get('https://firestore.googleapis.com/v1/projects/sitiosweb1/databases/(default)/documents/beauty_store_metadata/active_catalog',headers={'Authorization':'Bearer '+token},timeout=30)
    assert direct.status_code == 403, direct.status_code
    results = []
    for message in ['Find a moisturizer under $20.', 'Compare those recommendations by price and rating.']:
        payload.update(message=message,request_id=str(uuid4()))
        response = requests.post(API+'/api/chat',headers=headers,json=payload,timeout=100)
        response.raise_for_status()
        response.encoding = 'utf-8'
        frames = []
        for frame in response.text.split('\n\n'):
            event = next((line[7:] for line in frame.splitlines() if line.startswith('event: ')), None)
            data = next((json.loads(line[6:]) for line in frame.splitlines() if line.startswith('data: ')), None)
            if event:
                frames.append({'event':event,'data':data})
        results.append({'message':message,'frames':frames})
        (ROOT/'reports/cloud-smoke.json').write_text(json.dumps(results,indent=2))
        assert not any(f['event']=='error' for f in frames), frames
        assert any(f['event']=='done' for f in frames), frames
        recommended = [f for f in frames if f['event']=='recommendations']
        assert recommended and recommended[0]['data']['products'], frames
        for frame in recommended:
            rows = frame['data'].get('products',[]) if isinstance(frame['data'],dict) else frame['data']
            assert all(p['id'] in ids for p in rows)
            assert all(p['price_usd'] <= 20 for p in rows)
        print(json.dumps({'message':message,'events':[f['event'] for f in frames],'status':'passed'}))
    other = requests.post('https://identitytoolkit.googleapis.com/v1/accounts:signUp',
                          params={'key':config['apiKey']},json={'returnSecureToken':True},timeout=30)
    other.raise_for_status()
    assert requests.post(API+'/api/chat',json=payload,
                         headers={'Authorization':'Bearer '+other.json()['idToken']},timeout=30).status_code == 409
    print('Production auth, catalog, private database and two-turn chat checks passed.')

if __name__ == '__main__':
    main()
