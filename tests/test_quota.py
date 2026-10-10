from concurrent.futures import ThreadPoolExecutor
import pytest
from gateway.quota import MemoryQuota, LimitExceeded, SessionConflict, reserve_state


def test_turn_limit_and_replay():
    quota = MemoryQuota()
    quota.reserve('user', 'session', 'request-0')
    with pytest.raises(SessionConflict, match='progress'):
        quota.reserve('user', 'session', 'request-1')
    quota.finish('session', 'request-0', 'hello', 'reply')
    with pytest.raises(SessionConflict, match='already been processed'):
        quota.reserve('user', 'session', 'request-0')
    for i in range(1,10):
        _, turns = quota.reserve('user', 'session', f'request-{i}')
        assert turns == i+1
        quota.finish('session', f'request-{i}', 'hello', 'reply')
    with pytest.raises(LimitExceeded):
        quota.reserve('user', 'session', 'request-11')


def test_cross_user_isolation():
    quota = MemoryQuota()
    quota.reserve('a', 'session', 'request-1')
    quota.finish('session','request-1','private','private reply')
    with pytest.raises(SessionConflict, match='another visitor'):
        quota.reserve('b','session','request-2')
    history, _ = quota.reserve('b','new-session','request-3')
    assert history == []


def test_concurrent_global_conversation_limit():
    quota = MemoryQuota()
    def attempt(i):
        try:
            quota.reserve(str(i), f'session-{i}', str(i))
            return True
        except LimitExceeded:
            return False
    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(pool.map(attempt, range(150))) == 100
    assert next(iter(quota.months.values()))['turns'] == 100


def test_month_rollover_and_stale_request():
    quota = MemoryQuota()
    quota.reserve('a','s','first')
    quota.sessions['s']['busy_until'] = 0
    quota.reserve('a','s','second')
    quota.finish('s','first','bad','stale result')
    assert quota.sessions['s']['active_request'] == 'second'
    month, session = reserve_state(None, {'uid':'a','period':'2026-09','turns':10,'history':[{'role':'user','text':'old'}],'requests':[]}, 'a','new',0,'2026-10')
    assert session['history'] == [] and session['turns'] == 1
    assert month['conversations'] == 1


def test_global_turn_limit():
    with pytest.raises(LimitExceeded):
        reserve_state({'conversations': 99, 'turns':1000},None,'a','b',0,'2026-10')
