"""Read-only registry/monitoring discovery; API errors are reported without bodies."""
import json
from pathlib import Path
import requests
from google.auth.transport.requests import AuthorizedSession
from beauty.cloud import GcloudCredentials


def main():
    session = AuthorizedSession(GcloudCredentials.create())
    session.headers['x-goog-user-project'] = 'sitiosweb1'
    report = {'registry': [], 'metric_types': []}
    checks = session.get('https://monitoring.googleapis.com/v3/projects/sitiosweb1/uptimeCheckConfigs',timeout=30)
    report['existing_uptime_checks'] = len(checks.json().get('uptimeCheckConfigs',[])) if checks.status_code==200 else None
    for version in ['v1','v1alpha','v1beta']:
        discovery = session.get(f'https://agentregistry.googleapis.com/$discovery/rest?version={version}',timeout=30)
        if discovery.status_code == 200:
            Path('reports/registry-discovery.json').write_text(json.dumps(discovery.json(),indent=2))
        for region in ['global','us-central1']:
            response = session.get(f'https://agentregistry.googleapis.com/{version}/projects/sitiosweb1/locations/{region}/agents',timeout=30)
            report['registry'].append({'version':version,'region':region,'status':response.status_code,
                'agents':response.json().get('agents',[]) if response.status_code==200 else []})
        if any(item['status']==200 for item in report['registry']): break
    for prefix in ['aiplatform.googleapis.com/reasoning_engine','run.googleapis.com/container']:
        response = session.get('https://monitoring.googleapis.com/v3/projects/sitiosweb1/metricDescriptors',
            params={'filter':f'metric.type = starts_with("{prefix}")','pageSize':100},timeout=30)
        if response.status_code==200:
            report['metric_types'] += [item['type'] for item in response.json().get('metricDescriptors',[])]
            if prefix.startswith('aiplatform'):
                report['runtime_metric_descriptors'] = response.json().get('metricDescriptors',[])
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    response = session.get('https://monitoring.googleapis.com/v3/projects/sitiosweb1/timeSeries',params={
        'filter':'metric.type="aiplatform.googleapis.com/reasoning_engine/request_count"',
        'interval.endTime':now.isoformat(),'interval.startTime':(now-timedelta(days=7)).isoformat(),
        'view':'HEADERS','pageSize':10},timeout=30)
    report['runtime_metric_resources'] = [item['resource'] for item in response.json().get('timeSeries',[])] if response.status_code==200 else []
    Path('reports/cloud-preflight.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'registry_requests':[{k:v for k,v in item.items() if k!='agents'} for item in report['registry']],
        'metric_types':report['metric_types']}))


if __name__ == '__main__': main()
