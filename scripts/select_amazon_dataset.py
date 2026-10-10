"""Select exactly 100 real, complete skincare records with reachable image URLs."""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from beauty.models import Product

DATASET = 'https://huggingface.co/datasets/smartcat/Amazon_Beauty_and_Personal_Care_2023'
API = 'https://datasets-server.huggingface.co/rows?dataset=smartcat%2FAmazon_Beauty_and_Personal_Care_2023&config=default&split=train'


def clean(value):
    if isinstance(value, list):
        value = '\n'.join(str(v) for v in value)
    return BeautifulSoup(str(value or ''), 'html.parser').get_text(' ', strip=True)


def convert(row):
    categories = row.get('categories') or []
    if 'Skin Care' not in categories:
        raise ValueError('Outside skincare selection')
    title, description = clean(row.get('title')), clean(row.get('description'))
    if not description:
        description = clean(row.get('features'))
    images = list(dict.fromkeys(i.get('hi_res') or i.get('large') for i in row.get('images', []) if (i.get('hi_res') or i.get('large') or '').startswith('https://')))
    brand = row.get('brand')
    if not brand or str(brand).lower() == 'nan':
        brand = row.get('store') or None
    asin = row.get('parent_asin', '')
    subcategory = categories[2] if len(categories) > 2 else 'Skin Care'
    return Product(id=asin, source='amazon_us_2023', title=title, title_en=title,
        description=description, description_en=description, brand=brand, category=subcategory,
        features=[clean(row.get('features'))] if row.get('features') else [], image_urls=images[:20],
        source_url=f'https://www.amazon.com/dp/{asin}', price_source_usd=row.get('price'),
        rating=row.get('average_rating'), review_count=row.get('rating_number'),
        collected_at=datetime.now(timezone.utc), dataset_url=DATASET, source_snapshot='2023')


def image_available(url):
    try:
        with urlopen(Request(url, method='HEAD'), timeout=12) as response:
            return response.status == 200 and response.headers.get('Content-Type', '').startswith('image/')
    except Exception:
        return False


def main():
    directory = Path('data/amazon-2023')
    directory.mkdir(parents=True, exist_ok=True)
    Path('reports').mkdir(parents=True, exist_ok=True)
    products = {}
    failures = []
    for offset in range(0, 10000, 100):
        for attempt in range(3):
            try:
                with urlopen(f'{API}&offset={offset}&length=100', timeout=45) as response:
                    page = json.load(response)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        for entry in page['rows']:
            row = entry['row']
            try:
                product = convert(row)
                if product.id in products:
                    continue
                available = next((url for url in product.image_urls[:3] if image_available(url)), None)
                if not available:
                    raise ValueError('No reachable product image among first three candidates')
                product.image_urls = [available] + [u for u in product.image_urls if u != available]
                products[product.id] = product
            except Exception as exc:
                failures.append({'id': row.get('parent_asin'), 'reason': str(exc)[:250]})
            if len(products) == 100:
                break
        (directory / 'selected.json').write_text(json.dumps([p.model_dump(mode='json') for p in products.values()], indent=2, ensure_ascii=False), encoding='utf-8')
        report = {'dataset': DATASET, 'snapshot': '2023', 'scanned': offset+len(page['rows']), 'selected': len(products),
                  'image_check': 'HTTP HEAD 200 with image content type for each primary image', 'failures': failures,
                  'checked_at': datetime.now(timezone.utc).isoformat()}
        Path('reports/amazon-dataset-selection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'Scanned through row {offset+100}; selected {len(products)}/100', flush=True)
        if len(products) == 100:
            return
        time.sleep(.5)
    raise SystemExit('Could not find 100 complete skincare products; catalog not published')


if __name__ == '__main__':
    main()
