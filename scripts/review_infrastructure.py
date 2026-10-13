"""Read-only full Terraform plan. Private values/output stay in ignored reports."""
import json
import os
import subprocess
from pathlib import Path
from beauty.cloud import GcloudCredentials


def main():
    state = json.loads(Path('infra/terraform.tfstate').read_text())
    budgets = [r for r in state['resources'] if r['type'] == 'google_billing_budget' and r['name'] == 'store']
    if len(budgets) != 1: raise SystemExit('Require the existing store state; do not guess billing configuration')
    billing = budgets[0]['instances'][0]['attributes']['billing_account']
    managed_database = any(r['type']=='google_firestore_database' and r['name']=='store' for r in state['resources'])
    runtime = json.loads(Path('agent/deployment_metadata.json').read_text())['remote_agent_runtime_id']
    runtime = 'projects/sitiosweb1/' + runtime.split('/', 2)[2]
    env = os.environ.copy()
    env['GOOGLE_OAUTH_ACCESS_TOKEN'] = GcloudCredentials.create().token
    values = {'billing_account':billing, 'create_firestore':str(managed_database).lower(),
        'gateway_image':os.getenv('LUMA_GATEWAY_IMAGE','us-central1-docker.pkg.dev/sitiosweb1/beauty-store/api:v4-hardening'),
        'runtime_resource':runtime,
        'catalog_version':'c11ba6e461c161c0d3db440b7e0a1deac79ef1f969245612a51e67253ac2861c',
        'hosting_origin':'https://sitiosweb1-luma-beauty.web.app'}
    tf = str(Path('.tools/terraform/terraform.exe').resolve())
    result = subprocess.run([tf,'-chdir=infra','plan','-input=false','-out=hardening.tfplan',
        *[f'-var={key}={value}' for key,value in values.items()]], env=env, capture_output=True, text=True)
    Path('reports/infrastructure-plan-private.log').write_text(result.stdout + result.stderr)
    if result.returncode: raise SystemExit('Plan failed; inspect the private report')
    shown = subprocess.run([tf,'-chdir=infra','show','-json','hardening.tfplan'], capture_output=True, text=True, check=True)
    plan = json.loads(shown.stdout)
    changes = [{'resource':r['address'],'actions':r['change']['actions']} for r in plan['resource_changes'] if r['change']['actions'] != ['no-op']]
    destructive = [r for r in changes if 'delete' in r['actions']]
    report = {'changes':changes,'destructive_changes':destructive,'approved':False,
        'candidate_image_built':False,'plan_only':True}
    Path('reports/infrastructure-review.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))
    if destructive: raise SystemExit('Destructive changes require investigation; do not apply')


if __name__ == '__main__': main()
