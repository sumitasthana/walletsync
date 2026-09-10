"""Dump raw pricing page text (HTML → structured JSON) for reuse."""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from src.banks import get_bank

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# Required Schumer Box row substrings
REQUIRED_SUBSTRINGS = [
    "Annual",  # matches "Annual Fee" or "Annual Membership Fee"
    "Foreign Transaction",
    "Late Payment",
    "Cash Advance",  # matches both "Cash Advance APR" and "Cash Advance" fee row
    "Balance Transfer",
]


def extract_schumer_rows(html: str) -> dict:
    """
    Extract all table rows as label → value dict.
    Later rows with the same label OVERWRITE earlier ones.
    
    Args:
        html: Full page HTML
        
    Returns:
        Dict mapping row labels to cell values
    """
    soup = BeautifulSoup(html, 'html.parser')
    rows = {}
    
    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            
            label = cells[0].get_text(' ', strip=True)
            value = cells[1].get_text(' ', strip=True)
            
            if label and value:
                # Normalize whitespace
                label = ' '.join(label.split())
                value = ' '.join(value.split())
                rows[label] = value
    
    return rows


def extract_full_text(html: str) -> str:
    """
    Extract plain text from entire page.
    Fallback for fields not in tables (e.g., APR index disclosures).
    
    Args:
        html: Full page HTML
        
    Returns:
        Plain text with whitespace normalized
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Strip script/style tags
    for s in soup(['script', 'style']):
        s.decompose()
    
    text = soup.get_text(' ', strip=True)
    return ' '.join(text.split())  # Normalize whitespace


def validate_dump(rows: dict, card_id: str) -> list:
    """
    Validate that dump contains expected Schumer Box rows.
    
    Args:
        rows: Extracted schumer_rows dict
        card_id: Card identifier for logging
        
    Returns:
        List of missing required substrings (empty if all present)
    """
    present = set()
    for required in REQUIRED_SUBSTRINGS:
        if any(required.lower() in k.lower() for k in rows.keys()):
            present.add(required)
    
    missing = set(REQUIRED_SUBSTRINGS) - present
    if missing:
        log.warning(f"{card_id}: missing expected Schumer rows: {missing}")
    
    return list(missing)


def scrape_pricing_page_to_json(page: Page, url: str, card_id: str, card_name: str) -> dict:
    """
    Scrape pricing page and parse into structured JSON.
    
    Args:
        page: Playwright page object (reused)
        url: Pricing terms URL
        card_id: Card identifier
        card_name: Card name
        
    Returns:
        Dict with schumer_rows, full_page_text, and metadata
        
    Raises:
        Exception if scraping fails
    """
    log.info(f"Scraping: {url}")
    
    # Navigate to pricing page
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    
    # Wait for content to load
    time.sleep(3)
    
    # Get full page HTML
    content_html = page.content()
    
    # Extract structured data
    schumer_rows = extract_schumer_rows(content_html)
    full_page_text = extract_full_text(content_html)
    
    if not schumer_rows:
        raise Exception("Could not extract any table rows from page")
    
    log.info(f"  Found {len(schumer_rows)} table rows")
    
    # Validate dump
    missing = validate_dump(schumer_rows, card_id)
    
    # Build dump structure
    dump = {
        "card_id": card_id,
        "card_name": card_name,
        "pricing_terms_url": url,
        "dumped_at": datetime.now(timezone.utc).isoformat(),
        "schumer_rows": schumer_rows,
        "full_page_text": full_page_text,
    }
    
    if missing:
        dump["dump_warnings"] = [f"Missing expected rows: {', '.join(missing)}"]
    
    log.info(f"  ✓ Extracted {len(schumer_rows)} rows" + 
             (f" (warnings: {len(missing)} missing)" if missing else ""))
    
    return dump


def should_skip_dump(dump_path: str, force: bool) -> bool:
    """Check if dump should be skipped (exists and recent)."""
    if force:
        return False
    
    if not os.path.exists(dump_path):
        return False
    
    # Check if modified within last 24 hours
    mtime = os.path.getmtime(dump_path)
    age_hours = (time.time() - mtime) / 3600
    
    if age_hours < 24:
        log.info(f"  Skipping (dump exists, age: {age_hours:.1f}h)")
        return True
    
    return False


def write_dump_file(dump_path: str, dump_data: dict):
    """Write dump file as JSON."""
    with open(dump_path, 'w', encoding='utf-8') as f:
        json.dump(dump_data, f, indent=2, ensure_ascii=False)
    
    row_count = len(dump_data.get('schumer_rows', {}))
    log.info(f"  ✓ Wrote {row_count} rows to {os.path.basename(dump_path)}")


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Dump pricing page text")
    parser.add_argument('--bank', default='chase', help='Bank key (see src/banks/)')
    parser.add_argument('--force', action='store_true', help='Force re-dump even if files exist')
    parser.add_argument('--limit', type=int, help='Limit number of cards to process (for debugging)')
    args = parser.parse_args()
    
    bank = get_bank(args.bank)
    dump_dir = str(bank.raw_pricing_dir)
    
    # Ensure dump directory exists
    os.makedirs(dump_dir, exist_ok=True)
    
    # Load cleaned cards
    input_path = bank.cards_clean_path
    log.info(f"Loading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        cards = json.load(f)
    
    # Filter for cards with pricing_terms_url
    cards_with_pricing = [c for c in cards if c.get('pricing_terms_url')]
    log.info(f"Found {len(cards_with_pricing)} cards with pricing_terms_url")
    
    # Apply limit if specified
    if args.limit:
        cards_with_pricing = cards_with_pricing[:args.limit]
        log.info(f"Limited to {len(cards_with_pricing)} cards")
    
    log.info(f"Processing {len(cards_with_pricing)} cards")
    
    # Launch browser ONCE
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        
        success_count = 0
        skip_count = 0
        
        for idx, card in enumerate(cards_with_pricing, 1):
            card_id = card['card_id']
            card_name = card['card_name']
            pricing_url = card['pricing_terms_url']
            
            log.info(f"\n[{idx}/{len(cards_with_pricing)}] {card_name}")
            
            # Check if should skip
            dump_path = os.path.join(dump_dir, f"{card_id}.json")
            if should_skip_dump(dump_path, args.force):
                skip_count += 1
                continue
            
            try:
                # Scrape and parse to structured JSON
                dump_data = scrape_pricing_page_to_json(page, pricing_url, card_id, card_name)
                
                # Write dump file
                write_dump_file(dump_path, dump_data)
                success_count += 1
                
            except Exception as e:
                log.error(f"  ✗ Failed: {e}")
                continue
        
        browser.close()
    
    # Summary
    log.info(f"\n{'='*80}")
    log.info(f"SUMMARY")
    log.info(f"{'='*80}")
    log.info(f"✓ Dumped: {success_count}")
    log.info(f"⊘ Skipped: {skip_count}")
    log.info(f"✗ Failed: {len(cards_with_pricing) - success_count - skip_count}")
    log.info(f"Output: {dump_dir}")


if __name__ == '__main__':
    main()
