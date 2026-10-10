"""Activate an immutable catalog/index pair with one atomic pointer replacement."""
import json
import os
import uuid
from pathlib import Path
from beauty.catalog import Catalog


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def activate(products, bundle=None, directory='data'):
    catalog = Catalog(products, bundle)
    root = Path(directory)
    version_dir = root / 'catalogs' / catalog.version
    rows = [p.model_dump(mode='json') for p in products]
    atomic_json(version_dir / 'catalog.json', rows)
    if bundle:
        atomic_json(version_dir / 'retrieval-bundle.json', bundle)
    # Compatibility exports are not used by the live pointer reader.
    atomic_json(root / 'catalog.json', rows)
    if bundle:
        atomic_json(root / 'retrieval-bundle.json', bundle)
    pointer = {'version': catalog.version, 'catalog_path': f'catalogs/{catalog.version}/catalog.json',
               'retrieval_bundle_path': f'catalogs/{catalog.version}/retrieval-bundle.json' if bundle else None,
               'count': len(rows)}
    atomic_json(root / 'active-catalog.json', pointer)
    return pointer
