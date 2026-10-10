import pytest
from beauty.models import Product


@pytest.fixture
def product():
    # Test-only fixture; never imported into the real store database.
    return Product(id='B000000001', title='Test moisturizer', title_en='Test moisturizer', brand='Test fixture',
        description='A test description for a moisturizer for dry skin.', description_en='A test description for a moisturizer for dry skin.',
        category='Skin Care', image_urls=['https://example.com/test.jpg'], source_url='https://www.amazon.com.mx/dp/B000000001',
        price_mxn='180.00', rating=None, review_count=None, collected_at='2026-10-09T12:00:00Z')
