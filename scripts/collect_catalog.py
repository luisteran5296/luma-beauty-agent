"""One-time Amazon Mexico collector. Stops on blocks; never bypasses challenges."""
import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from beauty.models import Product

START_URL = 'https://www.amazon.com.mx/s?k=beauty&__mk_es_MX=%C3%85M%C3%85%C5%BD%C3%95%C3%91&crid=32IFRDHTAEMI3&sprefix=beauty%2Caps%2C177&ref=nb_sb_noss_1'


class CollectionBlocked(RuntimeError):
    pass


def text(soup, selector):
    node = soup.select_one(selector)
    return node.get_text(' ', strip=True) if node else ''


def number(value):
    match = re.search(r'[\d][\d,.]*', value.replace('\xa0', ''))
    return match.group().replace(',', '') if match else None


def parse_product(html, asin):
    soup = BeautifulSoup(html, 'html.parser')
    title = text(soup, '#productTitle')
    features = [x.get_text(' ', strip=True) for x in soup.select('#feature-bullets li .a-list-item') if x.get_text(strip=True)]
    description = text(soup, '#productDescription') or '\n'.join(features)
    price = text(soup, '#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen') or text(soup, '#corePrice_feature_div .a-price .a-offscreen')
    if not price:
        whole = text(soup, '#corePriceDisplay_desktop_feature_div .a-price-whole').rstrip('.,')
        fraction = text(soup, '#corePriceDisplay_desktop_feature_div .a-price-fraction')
        price = whole + '.' + (fraction or '00') if whole else ''
    images = []
    for image in soup.select('#imgTagWrapperId img, #landingImage, #imgBlkFront'):
        candidate = image.get('data-old-hires') or image.get('src')
        if candidate and candidate.startswith('https://') and candidate not in images:
            images.append(candidate)
    brand = text(soup, '#bylineInfo')
    brand = re.sub(r'^(Visita la tienda de|Marca:|Visit the .*? Store:?)\s*', '', brand, flags=re.I).strip() or None
    rating = number(text(soup, '#acrPopover .a-icon-alt'))
    reviews = number(text(soup, '#acrCustomerReviewText'))
    category = text(soup, '#wayfinding-breadcrumbs_feature_div li:last-child a') or 'Beauty'
    return Product(id=asin, title=title, brand=brand, description=description, features=features,
                   category=category, image_urls=images, source_url=f'https://www.amazon.com.mx/dp/{asin}',
                   price_mxn=number(price), rating=float(rating) if rating else None,
                   review_count=int(float(reviews)) if reviews else None, collected_at=datetime.now(timezone.utc))


def checkpoint(products, state, directory):
    directory.mkdir(parents=True, exist_ok=True)
    rows = [p.model_dump(mode='json') for p in products.values()]
    for name, payload in [('collected.json', rows), ('collection-state.json', state)]:
        temporary = directory / (name + '.tmp')
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(directory / name)
    if rows:
        with (directory / 'collected.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in row.items()} for row in rows)


def collect(args):
    directory = Path(args.output)
    products_path = directory / 'collected.json'
    products = {p.id: p for p in [Product.model_validate(x) for x in json.loads(products_path.read_text(encoding='utf-8'))]} if products_path.exists() else {}
    state_path = directory / 'collection-state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'next_url': START_URL, 'pending': [], 'attempted': [], 'failures': []}
    state.update(status='running', target=args.limit)
    attempted = set(state['attempted'])

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.visible)
        page = browser.new_page(locale='es-MX')

        def load(url):
            if urlparse(url).hostname not in ('www.amazon.com.mx', 'amazon.com.mx'):
                raise CollectionBlocked('Unexpected off-site link')
            for attempt in range(2):
                time.sleep(args.delay * (attempt + 1))
                response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
                html = page.content()
                if re.search(r'validateCaptcha|Type the characters you see|Escribe los caracteres|Robot Check', html, re.I):
                    raise CollectionBlocked('Amazon returned a challenge; collection paused')
                if response and response.status in (403, 429, 503):
                    if attempt == 1:
                        raise CollectionBlocked(f'Amazon returned HTTP {response.status}; collection paused')
                    continue
                if not response or response.status >= 400:
                    raise CollectionBlocked(f'Could not read page (HTTP {response.status if response else "unknown"})')
                return html

        try:
            while len(products) < args.limit:
                if not state['pending']:
                    if not state['next_url']:
                        state['status'] = 'incomplete'
                        break
                    soup = BeautifulSoup(load(state['next_url']), 'html.parser')
                    state['pending'] = list(dict.fromkeys(node.get('data-asin') for node in soup.select('[data-component-type="s-search-result"][data-asin]') if re.fullmatch(r'[A-Z0-9]{10}', node.get('data-asin', '')) and node.get('data-asin') not in attempted and node.get('data-asin') not in products))
                    next_link = soup.select_one('a.s-pagination-next')
                    state['next_url'] = urljoin(START_URL, next_link['href']) if next_link and next_link.get('href') else None
                    checkpoint(products, state, directory)
                    if not state['pending']:
                        raise CollectionBlocked('No product cards found; collection paused for inspection')
                asin = state['pending'][0]
                try:
                    products[asin] = parse_product(load(f'https://www.amazon.com.mx/dp/{asin}'), asin)
                except CollectionBlocked:
                    raise
                except Exception as exc:
                    state['failures'].append({'id': asin, 'reason': str(exc)[:1500]})
                attempted.add(asin)
                state['attempted'] = sorted(attempted)
                state['pending'].pop(0)
                checkpoint(products, state, directory)
            if len(products) >= args.limit:
                state['status'] = 'complete'
        except Exception as exc:
            state.update(status='blocked', reason=str(exc)[:1500])
        finally:
            state.update(collected=len(products), shortfall=max(0, args.limit - len(products)), updated_at=datetime.now(timezone.utc).isoformat())
            checkpoint(products, state, directory)
            browser.close()
    print(json.dumps({k: state.get(k) for k in ('status', 'collected', 'shortfall', 'reason')}, indent=2))
    return 0 if state['status'] == 'complete' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--output', default='data')
    parser.add_argument('--delay', type=float, default=3)
    parser.add_argument('--visible', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.limit <= 100 or args.delay < 2:
        parser.error('Use 1–100 products and at least 2 seconds between requests')
    raise SystemExit(collect(args))
