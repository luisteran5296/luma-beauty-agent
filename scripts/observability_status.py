"""Read-only native telemetry, incident and deployment evidence; private report."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from beauty.cloud import credentials
from google.auth.transport.requests import AuthorizedSession


def main():
    session=AuthorizedSession(credentials())
    session.headers['x-goog-user-project']='sitiosweb1'
    now=datetime.now(timezone.utc)
    report={'checked_at':now.isoformat(),'metrics':{}}
    for name in ['internal','completed','failed']:
        response=session.get('https://monitoring.googleapis.com/v3/projects/sitiosweb1/timeSeries',params={
            'filter':f'metric.type="logging.googleapis.com/user/luma_{name}"',
            'interval.startTime':(now-timedelta(minutes=30)).isoformat(),'interval.endTime':now.isoformat()},timeout=30)
        response.raise_for_status()
        report['metrics'][name]=response.json().get('timeSeries',[])
    response=session.get('https://monitoring.googleapis.com/v3/projects/719793696278/alerts',timeout=30)
    response.raise_for_status()
    report['incidents']=[a for a in response.json().get('alerts',[]) if
        'Luma' in json.dumps(a.get('policy',a.get('policySnapshot',{})))]
    response=session.get('https://monitoring.googleapis.com/v3/projects/sitiosweb1/alertPolicies',timeout=30)
    response.raise_for_status()
    report['policies']=[p for p in response.json().get('alertPolicies',[]) if p['displayName'].startswith('Luma:')]
    report['console_only']=all(not p.get('notificationChannels') for p in report['policies'])
    Path('reports/observability-status.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'metric_series':{k:len(v) for k,v in report['metrics'].items()},
        'policies':len(report['policies']),'console_only':report['console_only'],
        'incidents':[{'name':a.get('name'),'state':a.get('state')} for a in report['incidents']]}))


if __name__=='__main__': main()
