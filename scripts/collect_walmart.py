"""Resumable Walmart USD snapshot collector. Pause on any human-verification page."""
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from beauty.models import Product
from scripts.collect_catalog import CollectionBlocked, checkpoint

START_URL = 'https://www.walmart.com/search?q=skincare&facet=fulfillment_method%3AShipping'


def product_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from product_nodes(item)
    elif isinstance(value, dict):
        kind = value.get('@type', [])
        if kind == 'Product' or isinstance(kind, list) and 'Product' in kind:
            yield value
        if '@graph' in value:
            yield from product_nodes(value['@graph'])


def parse_product(html, item_id):
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            candidates.extend(product_nodes(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    # Never accidentally import a recommendation embedded in the detail page.
    matches = [p for p in candidates if re.search(r'/ip/(?:[^/]+/)?' + re.escape(item_id) + r'(?:[/?#]|$)', str(p.get('url', '')))]
    if len(matches) != 1:
        raise ValueError('No unambiguous product structured data matching the item URL')
    row = matches[0]
    offers = row.get('offers', {})
    if isinstance(offers, list):
        if len(offers) != 1:
            raise ValueError('Multiple offers require manual selection')
        offers = offers[0]
    if offers.get('priceCurrency') != 'USD':
        raise ValueError('Original USD price is absent')
    images = row.get('image', [])
    if isinstance(images, str):
        images = [images]
    images = [i.get('url', '') if isinstance(i, dict) else i for i in images]
    description = BeautifulSoup(row.get('description', ''), 'html.parser').get_text(' ', strip=True)
    brand = row.get('brand')
    if isinstance(brand, dict):
        brand = brand.get('name')
    rating = row.get('aggregateRating') or {}
    return Product(id=f'walmart-{item_id}', source='walmart_us', title=row.get('name', ''),
        title_en=row.get('name', ''), brand=brand, description=description, description_en=description,
        category=row.get('category') if isinstance(row.get('category'), str) else 'Skin Care',
        image_urls=images, source_url=f'https://www.walmart.com/ip/{item_id}',
        price_source_usd=offers.get('price'), rating=rating.get('ratingValue'),
        review_count=rating.get('reviewCount', rating.get('ratingCount')), collected_at=datetime.now(timezone.utc))


def collect(args):
    directory = Path(args.output)
    directory.mkdir(parents=True, exist_ok=True)
    saved = directory / 'collected.json'
    products = {p.id: p for p in (Product.model_validate(r) for r in json.loads(saved.read_text(encoding='utf-8')))} if saved.exists() else {}
    state_path = directory / 'collection-state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {
        'source': 'walmart_us', 'next_url': START_URL, 'pending': [], 'attempted': [], 'failures': []}
    if state.get('source') != 'walmart_us' or any(p.source != 'walmart_us' for p in products.values()):
        raise ValueError('Use a separate Walmart checkpoint directory')
    state.update(status='running', target=args.limit)
    attempted = set(state['attempted'])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale='en-US')

        def load(url):
            if urlparse(url).hostname not in ('walmart.com', 'www.walmart.com'):
                raise CollectionBlocked('Unexpected off-site link')
            for attempt in range(2):
                time.sleep(args.delay * (attempt + 1))
                response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
                html = page.content()
                if '/blocked' in page.url or re.search(r'Robot or human\?|confirm that you.re human|px-captcha', html, re.I):
                    raise CollectionBlocked('Walmart returned human verification; collection paused')
                if response and response.status in (403, 429, 503) and attempt == 0:
                    continue
                if not response or response.status >= 400:
                    raise CollectionBlocked(f'Walmart returned HTTP {response.status if response else "unknown"}')
                return html

        try:
            while len(products) < args.limit:
                if not state['pending']:
                    if not state['next_url']:
                        state['status'] = 'incomplete'
                        break
                    soup = BeautifulSoup(load(state['next_url']), 'html.parser')
                    ids = []
                    for link in soup.select('a[href]'):
                        match = re.fullmatch(r'/ip/(?:[^/]+/)?([0-9]{1,20})/?', urlparse(urljoin(START_URL, link['href'])).path)
                        if match and match[1] not in attempted and f'walmart-{match[1]}' not in products:
                            ids.append(match[1])
                    state['pending'] = list(dict.fromkeys(ids))
                    next_link = soup.select_one('a[rel="next"], a[aria-label="Next Page"], a[aria-label="Next page"]')
                    state['next_url'] = urljoin(START_URL, next_link['href']) if next_link and next_link.get('href') else None
                    checkpoint(products, state, directory)
                    if not state['pending']:
                        raise CollectionBlocked('No product links found; paused for inspection')
                item_id = state['pending'][0]
                try:
                    product = parse_product(load(f'https://www.walmart.com/ip/{item_id}'), item_id)
                    products[product.id] = product
                except CollectionBlocked:
                    raise
                except Exception as exc:
                    state['failures'].append({'id': item_id, 'reason': str(exc)[:1500]})
                attempted.add(item_id)
                state['attempted'] = sorted(attempted)
                state['pending'].pop(0)
                checkpoint(products, state, directory)
            if len(products) >= args.limit:
                state['status'] = 'complete'
                state.pop('reason', None)
        except Exception as exc:
            state.update(status='blocked', reason=str(exc)[:1500])
        finally:
            state.update(collected=len(products), shortfall=max(0, args.limit-len(products)), updated_at=datetime.now(timezone.utc).isoformat())
            checkpoint(products, state, directory)
            browser.close()
    print(json.dumps(state, indent=2))
    return 0 if state['status'] == 'complete' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--output', default='data/walmart')
    parser.add_argument('--delay', type=float, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100 or args.delay < 2:
        parser.error('Use 1–100 products and at least 2 seconds between requests')
    raise SystemExit(collect(args))
