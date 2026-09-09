"""Capture HTML fixtures for pricing parser tests."""
import time
from playwright.sync_api import sync_playwright

# Representative cards covering different formats
cards = [
    ('freedom-unlimited', 'https://sites.chase.com/services/creatives/pricingandterms.html/content/dam/pricingandterms/LGC60906.html?iCELL=6ZYD'),
    ('sapphire-reserve', 'https://sites.chase.com/services/creatives/pricingandterms.html/content/dam/pricingandterms/LGC61049.html?iCELL=6ZYD'),
    ('sapphire-reserve-business', 'https://sites.chase.com/services/creatives/pricingandterms.html/content/dam/pricingandterms/LGC63786.html?iCELL=6ZYD'),
    ('united-explorer', 'https://sites.chase.com/services/creatives/pricingandterms.html/content/dam/pricingandterms/LGC60777.html?iCELL=6ZYD'),
    ('freedom-rise', 'https://sites.chase.com/services/creatives/pricingandterms.html/content/dam/pricingandterms/LGC57233.html?iCELL=6ZYD'),
]

print("Capturing HTML fixtures...")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    for cid, url in cards:
        print(f"  Fetching {cid}...")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        
        with open(f'tests/fixtures/pricing_html/{cid}.html', 'w', encoding='utf-8') as f:
            f.write(page.content())
        print(f"    ✓ Saved to tests/fixtures/pricing_html/{cid}.html")
    
    browser.close()

print(f"\n✓ Captured {len(cards)} HTML fixtures")
