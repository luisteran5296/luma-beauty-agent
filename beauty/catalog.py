import hashlib
import json
import math
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from beauty.models import Product


def load_json(path):
    if path.startswith('gs://'):
        from google.cloud import storage
        bucket, name = path[5:].split('/', 1)
        return json.loads(storage.Client(project='sitiosweb1').bucket(bucket).blob(name).download_as_text())
    file = Path(path)
    return json.loads(file.read_text(encoding='utf-8')) if file.exists() else []


def fingerprint(products):
    payload = json.dumps([p.model_dump(mode='json') for p in sorted(products, key=lambda p: p.id)], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


class Catalog:
    def __init__(self, products, bundle=None):
        self.products = {p.id: p for p in products}
        if len(self.products) != len(products):
            raise ValueError('Duplicate product IDs')
        self.version = fingerprint(products)
        self.vectors = {}
        if bundle:
            if bundle['catalog_version'] != self.version:
                raise ValueError('Retrieval bundle and catalog versions differ')
            self.vectors = bundle['vectors']
            if set(self.vectors) != set(self.products):
                raise ValueError('Embedding IDs do not match catalog')
            if any(len(v) != 768 or not all(math.isfinite(x) for x in v) for v in self.vectors.values()):
                raise ValueError('Invalid embedding vector')

    def search(self, query='', max_price_usd=None, category=None, vector=None, limit=6):
        tokens = set(re.findall(r'\w+', query.lower()))
        ranked = []
        for product in self.products.values():
            if max_price_usd is not None and product.price_usd > max_price_usd:
                continue
            if category and category.lower() != product.category.lower():
                continue
            words = set(re.findall(r'\w+', product.document().lower()))
            lexical = len(tokens & words) / max(1, len(tokens))
            semantic = 0
            if vector is not None and product.id in self.vectors:
                candidate = self.vectors[product.id]
                if len(vector) != len(candidate):
                    raise ValueError('Query embedding dimension mismatch')
                denominator = math.sqrt(sum(x*x for x in vector) * sum(x*x for x in candidate))
                semantic = sum(a*b for a, b in zip(vector, candidate)) / denominator if denominator else 0
            if query and lexical == 0 and (vector is None or semantic < .25):
                continue
            ranked.append((.7 * semantic + .3 * lexical, product.id, product))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        return [row[2] for row in ranked[:limit]]


@lru_cache(maxsize=2)
def _cloud_pointer(refresh_window):
    from google.cloud import firestore
    pointer = firestore.Client(project='sitiosweb1').collection('beauty_store_metadata').document('active_catalog').get().to_dict()
    if not pointer or not pointer.get('catalog_path') or not pointer.get('retrieval_bundle_path'):
        raise RuntimeError('Active Firestore catalog requires product and embedding snapshot paths')
    return pointer


@lru_cache(maxsize=4)
def _snapshot(catalog_path, bundle_path, version):
    catalog = Catalog([Product.model_validate(row) for row in load_json(catalog_path)], load_json(bundle_path) if bundle_path else None)
    if isinstance(version, str) and catalog.version != version:
        raise RuntimeError('Active catalog pointer does not match snapshot')
    return catalog


def get_catalog():
    if os.getenv('CATALOG_BACKEND') == 'firestore':
        pointer = _cloud_pointer(int(time.monotonic() // 30))
        catalog = _snapshot(pointer['catalog_path'], pointer['retrieval_bundle_path'], pointer['version'])
    elif os.getenv('CATALOG_PATH'):
        # Explicit paths remain supported for tests/evaluations and legacy installations.
        catalog_path = os.environ['CATALOG_PATH']
        bundle_path = os.getenv('RETRIEVAL_BUNDLE_PATH', '')
        stamp = tuple(Path(p).stat().st_mtime_ns if p and not p.startswith('gs://') and Path(p).exists() else 0 for p in (catalog_path, bundle_path))
        catalog = _snapshot(catalog_path, bundle_path, stamp)
    elif Path(os.getenv('CATALOG_POINTER_PATH', 'data/active-catalog.json')).exists():
        path = Path(os.getenv('CATALOG_POINTER_PATH', 'data/active-catalog.json'))
        pointer = load_json(str(path))
        catalog = _snapshot(str(path.parent / pointer['catalog_path']), str(path.parent / pointer['retrieval_bundle_path']) if pointer.get('retrieval_bundle_path') else '', pointer['version'])
    else:
        path = Path('data/catalog.json')
        catalog = _snapshot(str(path), '', (path.stat().st_mtime_ns if path.exists() else 0,))
    if os.getenv('ENVIRONMENT') == 'production' and (len(catalog.products) != 100 or not catalog.vectors or any(not p.title_en or not p.description_en for p in catalog.products.values())):
        raise RuntimeError('Production requires 100 English-translated products and matching embeddings')
    return catalog
