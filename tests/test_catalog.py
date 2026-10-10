import json
from decimal import Decimal
from pathlib import Path
import pytest
from pydantic import ValidationError
from beauty.models import Product
from beauty.catalog import Catalog, fingerprint
from scripts.collect_catalog import parse_product, checkpoint
from scripts.import_catalog import read_products


def test_currency_rounding(product):
    assert product.price_usd == Decimal('10.00')
    product.price_mxn = Decimal('180.09')
    assert product.price_usd == Decimal('10.01')


def test_source_and_rating_validation(product):
    row = product.model_dump(mode='json')
    with pytest.raises(ValidationError):
        Product.model_validate({**row, 'source_url': 'https://example.com/dp/B000000001'})
    with pytest.raises(ValidationError):
        Product.model_validate({**row, 'rating': 6})
    assert Product.model_validate(row).rating is None


def test_filters_and_duplicate_detection(product):
    catalog = Catalog([product])
    assert catalog.search('moisturizer', max_price_usd=9) == []
    assert catalog.search('moisturizer', category='Hair Care') == []
    assert catalog.search('moisturizer', category='Skin Care') == [product]
    assert catalog.search('unknown-term') == []
    with pytest.raises(ValueError, match='Duplicate'):
        Catalog([product, product])


def test_embedding_versions_and_hard_filter(product):
    bundle = {'catalog_version': fingerprint([product]), 'vectors': {product.id: [1.0]+[0.0]*767}}
    catalog = Catalog([product], bundle)
    assert catalog.search('different-term', vector=[1.0]+[0.0]*767) == [product]
    assert catalog.search('different-term', vector=[1.0]+[0.0]*767, max_price_usd=9) == []
    with pytest.raises(ValueError, match='versions differ'):
        Catalog([product], {**bundle, 'catalog_version': 'invalid'})


def test_import_checkpoint_roundtrip(product, tmp_path):
    state = {'pending': ['B000000002'], 'status': 'blocked'}
    checkpoint({product.id: product}, state, tmp_path)
    assert read_products(tmp_path / 'collected.json')[0] == product
    assert read_products(tmp_path / 'collected.csv')[0] == product
    assert json.loads((tmp_path / 'collection-state.json').read_text())['pending'] == ['B000000002']


def test_amazon_parser_missing_rating():
    html = '''<span id="productTitle">Fixture moisturizer</span>
    <div id="feature-bullets"><li><span class="a-list-item">For dry skin in a test fixture.</span></li></div>
    <div id="corePrice_feature_div"><span class="a-price"><span class="a-offscreen">$1,299.00</span></span></div>
    <img id="landingImage" src="https://example.com/test.jpg">'''
    row = parse_product(html, 'B000000001')
    assert row.price_mxn == Decimal('1299.00')
    assert row.rating is None
    assert row.description.startswith('For dry skin')


def test_real_catalog_is_not_test_fixtures():
    rows = json.loads(Path('data/catalog.json').read_text(encoding='utf-8'))
    assert not any(row['id'].startswith('B00000000') for row in rows)
