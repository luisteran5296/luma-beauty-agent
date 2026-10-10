"""Build and release only the dedicated Luma Firebase Hosting site."""
import gzip
import hashlib
import json
import os
import subprocess
from scripts.deploy_cloud import ROOT, SITE, session, request

def main():
    gateway = subprocess.check_output([str(ROOT/'.tools/terraform/terraform.exe'), '-chdir=infra',
                                      'output', '-raw', 'gateway_url'], cwd=ROOT, text=True).strip()
    config = json.loads((ROOT/'reports/firebase-web-config.json').read_text())
    env = os.environ.copy()
    env.update(VITE_API_BASE=gateway, VITE_FIREBASE_API_KEY=config['apiKey'], VITE_FIREBASE_APP_ID=config['appId'])
    subprocess.run(['npm.cmd','run','build'], cwd=ROOT/'frontend', env=env, check=True)
    dist = ROOT/'frontend/dist'
    files, blobs = {}, {}
    for path in dist.rglob('*'):
        if path.is_file():
            data = gzip.compress(path.read_bytes(), mtime=0)
            digest = hashlib.sha256(data).hexdigest()
            files['/'+path.relative_to(dist).as_posix()] = digest
            blobs[digest] = data
    s = session()
    base = 'https://firebasehosting.googleapis.com/v1beta1/'
    config = {'rewrites':[{'glob':'**','path':'/index.html'}],
              'headers':[{'glob':'**','headers':{'X-Content-Type-Options':'nosniff',
              'Referrer-Policy':'strict-origin-when-cross-origin','X-Frame-Options':'DENY'}}]}
    version = request(s,'POST',base+f'sites/{SITE}/versions',json={'config':config})['name']
    population = request(s,'POST',base+version+':populateFiles',json={'files':files})
    for digest in population.get('uploadRequiredHashes',[]):
        r = s.post(population['uploadUrl']+'/'+digest, data=blobs[digest],
                   headers={'Content-Type':'application/octet-stream'},timeout=90)
        r.raise_for_status()
    request(s,'PATCH',base+version,params={'updateMask':'status'},json={'status':'FINALIZED'})
    release = request(s,'POST',base+f'sites/{SITE}/releases',params={'versionName':version},json={})
    (ROOT/'reports/hosting-release.json').write_text(json.dumps(release,indent=2))
    print(json.dumps({'url':f'https://{SITE}.web.app','version':version,'file_count':len(files)}))

if __name__ == '__main__':
    main()
