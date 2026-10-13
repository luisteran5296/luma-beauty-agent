"""Read-only rollback evidence. Saves no tokens; all output is private/ignored."""
import json
import subprocess
from pathlib import Path
from google.auth.transport.requests import AuthorizedSession
from beauty.cloud import GcloudCredentials


def main():
    session = AuthorizedSession(GcloudCredentials.create())
    session.headers['x-goog-user-project'] = 'sitiosweb1'
    metadata = json.loads(Path('agent/deployment_metadata.json').read_text())
    resource = metadata['remote_agent_runtime_id']
    agent = session.get(f'https://us-central1-aiplatform.googleapis.com/v1beta1/{resource}',timeout=30)
    gateway = session.get('https://run.googleapis.com/v2/projects/sitiosweb1/locations/us-central1/services/beauty-store-api',timeout=30)
    agent.raise_for_status(); gateway.raise_for_status()
    def artifacts(value):
        if isinstance(value,dict): return [v for item in value.values() for v in artifacts(item)]
        if isinstance(value,list): return [v for item in value for v in artifacts(item)]
        return [value] if isinstance(value,str) and ('.pkg.dev/' in value or value.startswith('gs://')) else []
    previous_commit = subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip()
    archive = Path('reports') / ('rollback-source-'+previous_commit[:12]+'.tar')
    if not archive.exists():
        subprocess.run(['git','archive','--format=tar','--output='+str(archive),previous_commit],check=True)
    existing = {'gateway_revision':gateway.json().get('latestReadyRevision'),
        'gateway_images':artifacts(gateway.json().get('template',{})),
        'agent_resource':resource,'agent_artifacts':artifacts(agent.json()),
        'agent_source':agent.json().get('spec',{}).get('sourceCodeSpec',{}),
        'agent_spec':agent.json().get('spec',{}),'retained':True,
        'previous_source_commit':previous_commit,'previous_source_archive':str(archive),
        'agent_source_input_only':not bool(artifacts(agent.json()))}
    commit = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    evaluation = json.loads(Path('reports/hardening-final-evaluation.json').read_text())
    quality = json.loads(Path('reports/native-offline-evaluation.json').read_text())
    report = {'candidate_commit':commit,'shopping_code_hash':evaluation['candidate_code_hash'],
        'catalog_version':evaluation['catalog_version'],'deployment_status':'candidate-not-deployed',
        'native_quality_gate_passed':quality.get('release_gate_passed',False),
        'previous_deployment':existing}
    Path('reports/release-evidence.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'candidate_commit':commit,'rollback_artifacts_found':bool(existing['gateway_images']) and archive.exists(),
        'native_quality_gate_passed':report['native_quality_gate_passed']}))


if __name__ == '__main__': main()
