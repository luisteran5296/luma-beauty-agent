"""Artificial structured-data fixtures are only used by tests."""
import json
from decimal import Decimal
import pytest
from pydantic import ValidationError
from scripts.collect_walmart import parse_product
from scripts.collect_catalog import checkpoint
from scripts.import_catalog import read_products
from beauty.models import Product


def fixture_html(**overrides):
    row = {'@type': 'Product', 'url': 'https://www.walmart.com/ip/Fixture/123456',
           'name': 'Fixture moisturizer', 'description': '<p>Test-only moisturizer description.</p>',
           'image': ['https://example.com/test.jpg'], 'brand': {'name': 'Fixture'},
           'offers': {'priceCurrency': 'USD', 'price': '12.99'}}
    row.update(overrides)
    return '<script type="application/ld+json">' + json.dumps({'@graph': [row]}) + '</script>'


def test_original_usd_and_nullable_rating():
    product = parse_product(fixture_html(), '123456')
    assert product.id == 'walmart-123456'
    assert product.price_usd == Decimal('12.99')
    assert product.price_mxn is None
    assert product.rating is None
    assert product.public()['price_mxn'] is None
    assert product.description_en == 'Test-only moisturizer description.'


def test_reject_wrong_item_currency_and_mixed_prices():
    with pytest.raises(ValueError):
        parse_product(fixture_html(), '999999')
    with pytest.raises(ValueError):
        parse_product(fixture_html(offers={'priceCurrency': 'MXN', 'price': '12.99'}), '123456')
    product = parse_product(fixture_html(), '123456')
    with pytest.raises(ValidationError):
        Product.model_validate({**product.model_dump(), 'price_mxn': '180.00'})
    with pytest.raises(ValidationError):
        Product.model_validate({**product.model_dump(), 'source_url': 'https://www.walmart.com/ip/999999'})


def test_walmart_json_and_csv_recovery(tmp_path):
    product = parse_product(fixture_html(), '123456')
    checkpoint({product.id: product}, {'status': 'blocked', 'pending': ['999999']}, tmp_path)
    assert read_products(tmp_path / 'collected.json') == [product]
    assert read_products(tmp_path / 'collected.csv') == [product]
