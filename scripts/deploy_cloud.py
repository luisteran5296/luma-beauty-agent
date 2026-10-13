"""Explicit deployment operations for the user-approved Luma store."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from beauty.cloud import GcloudCredentials
from google.auth.transport.requests import AuthorizedSession

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'sitiosweb1'
SITE = 'sitiosweb1-luma-beauty'

def session():
    s = AuthorizedSession(GcloudCredentials.create())
    s.headers['x-goog-user-project'] = PROJECT
    return s

def request(s, method, url, **kwargs):
    r = s.request(method, url, timeout=90, **kwargs)
    r.raise_for_status()
    return r.json() if r.content else {}

def terraform(action):
    env = os.environ.copy()
    env['GOOGLE_OAUTH_ACCESS_TOKEN'] = GcloudCredentials.create().token
    tf = str(ROOT / '.tools/terraform/terraform.exe')
    full = action.endswith('-full')
    command = action.removesuffix('-full')
    args = [tf, '-chdir=infra', command, '-input=false']
    if command == 'plan':
        runtime = 'pending'
        if full:
            metadata = json.loads((ROOT/'agent/deployment_metadata.json').read_text())
            runtime = metadata.get('remote_agent_runtime_id') or metadata.get('pending_operation', {}).get('operation_name', '').split('/operations/')[0] or os.getenv('LUMA_RUNTIME_RESOURCE')
            if not runtime:
                raise RuntimeError('Deploy Agent Runtime before planning the gateway')
            runtime = 'projects/sitiosweb1/' + runtime.split('/', 2)[2]
        billing_account = os.environ.get('LUMA_BILLING_ACCOUNT')
        if not billing_account:
            raise RuntimeError('Set LUMA_BILLING_ACCOUNT to your billing account before planning')
        args += [f'-var=billing_account={billing_account}', f'-var=create_firestore={os.getenv("LUMA_CREATE_FIRESTORE", "false")}',
                 f'-var=gateway_image={os.getenv("LUMA_GATEWAY_IMAGE", "us-central1-docker.pkg.dev/sitiosweb1/beauty-store/api:v3")}', f'-var=runtime_resource={runtime}',
                 '-var=catalog_version=c11ba6e461c161c0d3db440b7e0a1deac79ef1f969245612a51e67253ac2861c', f'-var=hosting_origin=https://{SITE}.web.app']
        targets = ['google_project_service.apis', 'google_service_account.agent',
          'google_service_account.gateway', 'google_project_iam_member.agent_vertex',
          'google_project_iam_member.gateway_vertex', 'google_project_iam_member.gateway_firestore',
          'google_project_iam_member.agent_firestore', 'google_storage_bucket.catalog',
          'google_project_iam_member.agent_api_usage', 'google_project_iam_member.gateway_api_usage',
          'google_project_iam_member.agent_trace',
          'google_storage_bucket_iam_member.readers', 'google_firestore_database.store',
          'google_artifact_registry_repository.store', 'google_billing_budget.store']
        if not full:
            args += [f'-target={t}' for t in targets]
        args += ['-out=deployment.tfplan' if full else '-out=foundations.tfplan']
    else:
        args += ['deployment.tfplan' if full else 'foundations.tfplan']
    subprocess.run(args, env=env, cwd=ROOT, check=True)

def firebase_setup():
    s = session()
    base = 'https://firebase.googleapis.com/v1beta1/'
    r = s.get(base + f'projects/{PROJECT}')
    if r.status_code == 404:
        op = request(s, 'POST', base + f'projects/{PROJECT}:addFirebase', json={})
        print(json.dumps({'firebase_operation': op['name']}))
        return
    r.raise_for_status()
    apps = request(s, 'GET', base + f'projects/{PROJECT}/webApps').get('apps', [])
    app = next((a for a in apps if a.get('displayName') == 'Luma Beauty'), None)
    if not app:
        op = request(s, 'POST', base + f'projects/{PROJECT}/webApps', json={'displayName':'Luma Beauty'})
        print(json.dumps({'web_app_operation': op['name']}))
        return
    config = request(s, 'GET', base + app['name'] + '/config')
    (ROOT/'reports/firebase-web-config.json').write_text(json.dumps(config, indent=2))
    hosting = 'https://firebasehosting.googleapis.com/v1beta1/'
    sites = request(s, 'GET', hosting + f'projects/{PROJECT}/sites').get('sites', [])
    if not any(a['name'].endswith('/'+SITE) for a in sites):
        request(s, 'POST', hosting + f'projects/{PROJECT}/sites', params={'siteId':SITE}, json={})
    auth = f'https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}/config'
    r = s.get(auth)
    if r.status_code == 404:
        request(s, 'POST', f'https://identitytoolkit.googleapis.com/v2/projects/{PROJECT}/identityPlatform:initializeAuth', json={})
    else:
        r.raise_for_status()
    existing = request(s, 'GET', auth)
    domains = list(dict.fromkeys(existing.get('authorizedDomains', []) + [f'{SITE}.web.app', f'{SITE}.firebaseapp.com']))
    request(s, 'PATCH', auth, params={'updateMask':'signIn.anonymous.enabled,authorizedDomains'},
            json={'signIn':{'anonymous':{'enabled':True}},'authorizedDomains':domains})
    print(json.dumps({'firebase_ready':True, 'site':SITE, 'app_id':config['appId']}))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['plan','apply','plan-full','apply-full','firebase'])
    a = p.parse_args()
    firebase_setup() if a.action == 'firebase' else terraform(a.action)
