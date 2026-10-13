"""Dry-run by default. Reviewed rollout only: timestamp existing store sessions."""
import argparse
import json
from datetime import datetime, timezone
from google.cloud import firestore
from beauty.cloud import credentials
from gateway.quota import RETENTION_SECONDS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    db = firestore.Client(project='sitiosweb1',credentials=credentials())
    pending = []
    for snapshot in db.collection('beauty_store_sessions').stream():
        value = snapshot.to_dict()
        if value.get('expires_at'): continue
        stamp = value.get('updated_at', snapshot.update_time.timestamp())
        pending.append((snapshot.reference,datetime.fromtimestamp(stamp+RETENTION_SECONDS,timezone.utc)))
    if args.apply:
        for start in range(0,len(pending),400):
            batch = db.batch()
            for ref,expires in pending[start:start+400]: batch.update(ref,{'expires_at':expires})
            batch.commit()
    print(json.dumps({'legacy_sessions':len(pending),'applied':args.apply}))


if __name__ == '__main__': main()
