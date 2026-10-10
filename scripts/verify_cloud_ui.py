"""Verify the public storefront and its real cloud-backed agent in Chromium."""
import json
from time import monotonic
from playwright.sync_api import sync_playwright
from scripts.deploy_cloud import ROOT, SITE

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':1440,'height':1000})
        errors = []
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(f'https://{SITE}.web.app')
        page.locator('.product-card').first.wait_for()
        assert page.locator('.product-card').count() == 100
        page.get_by_role('button',name='Talk to Luma',exact=False).click()
        composer = page.get_by_label('Message your beauty guide',exact=True)
        composer.fill('Find a moisturizer under $20.')
        started = monotonic()
        page.get_by_role('button',name='Send message',exact=True).click()
        page.wait_for_function("!document.querySelector('#chat-input').disabled",timeout=100000)
        assert page.locator('.chat-error').count() == 0
        assert page.locator('.message.assistant').count() == 1
        cards = page.locator('.chat-product').count()
        assert cards > 0
        page.screenshot(path=str(ROOT/'reports/cloud-live-chat.png'))
        assert not errors, errors
        report = {'url':page.url,'cards':cards,'page_errors':errors,'latency_seconds':round(monotonic()-started,2),
                  'assistant_text':page.locator('.message.assistant p').inner_text()}
        (ROOT/'reports/cloud-live-ui.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='assistant_text'}))
        browser.close()

if __name__ == '__main__':
    main()
