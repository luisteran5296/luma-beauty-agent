import json
from decimal import Decimal
from beauty.catalog import get_catalog, fingerprint, Catalog
from beauty.snapshots import activate


def bundle(products):
    return {'catalog_version': fingerprint(products), 'vectors': {p.id: [1.0]+[0.0]*767 for p in products}}


def test_live_catalog_refreshes_prices_text_and_vectors_together(product, tmp_path, monkeypatch):
    monkeypatch.delenv('CATALOG_BACKEND', raising=False)
    monkeypatch.delenv('CATALOG_PATH', raising=False)
    monkeypatch.setenv('CATALOG_POINTER_PATH', str(tmp_path / 'active-catalog.json'))
    first = activate([product], bundle([product]), tmp_path)
    old = get_catalog()
    changed = product.model_copy(deep=True)
    changed.price_mxn = Decimal('360.00')
    changed.title_en = 'Updated cleanser'
    changed.description_en = 'An updated cleanser description from the catalog.'
    second = activate([changed], bundle([changed]), tmp_path)
    new = get_catalog()
    assert first['version'] != second['version']
    assert old.products[product.id].price_usd == Decimal('10.00')
    assert new.products[product.id].price_usd == Decimal('20.00')
    assert new.search('cleanser')[0].title_en == 'Updated cleanser'
    assert new.version == second['version']
    assert set(new.vectors) == {product.id}


def test_bad_refresh_does_not_replace_active_catalog(product, tmp_path):
    import pytest
    activate([product], bundle([product]), tmp_path)
    before = (tmp_path / 'active-catalog.json').read_text()
    changed = product.model_copy(update={'description_en': 'Changed description'})
    with pytest.raises(ValueError, match='versions differ'):
        activate([changed], bundle([product]), tmp_path)
    assert (tmp_path / 'active-catalog.json').read_text() == before


def test_real_selected_catalog_and_images():
    from scripts.import_catalog import read_products
    from pathlib import Path
    rows = read_products('data/catalog.json')
    assert len(rows) == len({p.id for p in rows}) == 100
    assert all(p.source == 'amazon_us_2023' and p.price_usd > 0 and p.source_snapshot == '2023' for p in rows)
    assert all(p.image_urls and p.title_en and p.description_en for p in rows)
    index = json.loads(Path('data/retrieval-bundle.json').read_text())
    assert len(Catalog(rows, index).vectors) == 100
