import hashlib
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo


class LimitExceeded(Exception):
    pass


class SessionConflict(Exception):
    pass


def month_key():
    return datetime.now(ZoneInfo('America/Mexico_City')).strftime('%Y-%m')


def reserve_state(month, session, uid, request_id, now, period):
    month = dict(month or {'conversations': 0, 'turns': 0})
    session = dict(session or {'uid': uid, 'period': period, 'turns': 0, 'history': [], 'requests': []})
    if session['uid'] != uid:
        raise SessionConflict('Session belongs to another visitor')
    if session.get('busy_until', 0) > now:
        raise SessionConflict('A response is already in progress')
    if session['period'] != period:
        session.update(period=period, turns=0, history=[], requests=[])
    if request_id in session['requests']:
        raise SessionConflict('This request has already been processed')
    if session['turns'] >= 10 or month['turns'] >= 1000:
        raise LimitExceeded('The demo chat allowance has been reached')
    if session['turns'] == 0:
        if month['conversations'] >= 100:
            raise LimitExceeded('The monthly conversation allowance has been reached')
        month['conversations'] += 1
    month['turns'] += 1
    session['turns'] += 1
    session['requests'] = (session['requests'] + [request_id])[-10:]
    session.update(busy_until=now + 120, active_request=request_id, updated_at=now)
    return month, session


class MemoryQuota:
    """Single-process local development only. Production uses Firestore transactions."""
    def __init__(self):
        self.months, self.sessions, self.lock = {}, {}, threading.Lock()

    def reserve(self, uid, session_id, request_id):
        with self.lock:
            period = month_key()
            month, session = reserve_state(self.months.get(period), self.sessions.get(session_id), uid, request_id, time.time(), period)
            self.months[period], self.sessions[session_id] = month, session
            return session['history'], session['turns']

    def finish(self, session_id, request_id, message, answer, product_ids=None):
        with self.lock:
            session = self.sessions[session_id]
            if session.get('active_request') != request_id:
                return
            history = session['history'] + ([{'role': 'user', 'text': message}, {'role': 'assistant', 'text': answer, 'product_ids': list(product_ids or [])[:3]}] if answer else [])
            session.update(history=history[-12:], busy_until=0, active_request=None)


class FirestoreQuota:
    def __init__(self, db):
        self.db = db

    def ref(self, session_id):
        return self.db.collection('beauty_store_sessions').document(hashlib.sha256(session_id.encode()).hexdigest())

    def reserve(self, uid, session_id, request_id):
        from google.cloud import firestore
        period = month_key()
        monthly = self.db.collection('beauty_store_quotas').document(period)
        session_ref = self.ref(session_id)

        @firestore.transactional
        def apply(transaction):
            # Read all documents before writing; retry conflicts atomically across instances.
            month = monthly.get(transaction=transaction).to_dict()
            session = session_ref.get(transaction=transaction).to_dict()
            month, session = reserve_state(month, session, uid, request_id, time.time(), period)
            transaction.set(monthly, month)
            transaction.set(session_ref, session)
            return session['history'], session['turns']
        return apply(self.db.transaction())

    def finish(self, session_id, request_id, message, answer, product_ids=None):
        from google.cloud import firestore
        ref = self.ref(session_id)

        @firestore.transactional
        def apply(transaction):
            session = ref.get(transaction=transaction).to_dict()
            if not session or session.get('active_request') != request_id:
                return
            history = session['history'] + ([{'role': 'user', 'text': message}, {'role': 'assistant', 'text': answer, 'product_ids': list(product_ids or [])[:3]}] if answer else [])
            transaction.update(ref, {'history': history[-12:], 'busy_until': 0, 'active_request': None})
        apply(self.db.transaction())
