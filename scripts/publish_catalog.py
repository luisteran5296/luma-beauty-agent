"""Post-approval publication of a validated catalog to GCS and namespaced Firestore."""
import argparse
import json
from pathlib import Path
from google.cloud import firestore, storage
from beauty.catalog import Catalog, fingerprint
from scripts.import_catalog import read_products
from beauty.cloud import credentials


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bucket', default='sitiosweb1-beauty-store-catalog')
    parser.add_argument('--approved', action='store_true', help='Use only after user approves cloud deployment')
    args = parser.parse_args()
    if not args.approved:
        raise SystemExit('Cloud publication is pending user approval. No changes made.')
    products = read_products('data/catalog.json')
    if len(products) != 100 or any(not p.title_en or not p.description_en for p in products):
        raise SystemExit('Publication requires 100 complete English-translated products')
    bundle = json.loads(Path('data/retrieval-bundle.json').read_text(encoding='utf-8'))
    Catalog(products, bundle)
    version = fingerprint(products)
    cloud_credentials = credentials()
    bucket = storage.Client(project='sitiosweb1', credentials=cloud_credentials).bucket(args.bucket)
    rows = [p.model_dump(mode='json') for p in products]
    for name, payload in [('catalog.json', rows), ('retrieval-bundle.json', bundle)]:
        bucket.blob(f'catalogs/{version}/{name}').upload_from_string(json.dumps(payload, ensure_ascii=False), content_type='application/json')
    db = firestore.Client(project='sitiosweb1', credentials=cloud_credentials)
    batch = db.batch()
    parent = db.collection('beauty_store_catalogs').document(version)
    for row in rows:
        batch.set(parent.collection('products').document(row['id']), row)
    batch.set(parent, {'version': version, 'count': 100})
    batch.set(db.collection('beauty_store_metadata').document('active_catalog'), {'version': version,
        'catalog_path': f'gs://{args.bucket}/catalogs/{version}/catalog.json',
        'retrieval_bundle_path': f'gs://{args.bucket}/catalogs/{version}/retrieval-bundle.json'})
    batch.commit()
    print(json.dumps({'catalog_version': version, 'catalog_path': f'gs://{args.bucket}/catalogs/{version}/catalog.json', 'retrieval_bundle_path': f'gs://{args.bucket}/catalogs/{version}/retrieval-bundle.json'}, indent=2))


if __name__ == '__main__':
    main()
