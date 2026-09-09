"""Chase credit card scraper using Playwright (headless)."""

import json
import logging
import os
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

URL = "https://creditcards.chase.com/all-credit-cards?iCELL=6ZYD"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "chase_cards.json")


def _text(element):
    """Return stripped inner text or None."""
    if element is None:
        return None
    txt = element.inner_text()
    return txt.strip() if txt else None


def _href(element):
    """Return href attribute or None."""
    if element is None:
        return None
    return element.get_attribute("href")


def scroll_page(page, pause=0.8, step=600):
    """Scroll the page incrementally to trigger lazy-loaded content."""
    log.info("Scrolling page to trigger lazy-loaded elements...")
    prev_height = 0
    while True:
        page.evaluate(f"window.scrollBy(0, {step})")
        time.sleep(pause)
        curr_height = page.evaluate("window.scrollY")
        total_height = page.evaluate("document.body.scrollHeight")
        if curr_height + page.evaluate("window.innerHeight") >= total_height:
            break
        if curr_height == prev_height:
            break
        prev_height = curr_height
    # Scroll back to top
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)
    log.info("Scrolling complete.")


def extract_card(card_el):
    """Extract data from a single card container element."""
    data = {
        "card_name": None,
        "details_url": None,
        "annual_fee": None,
        "apr_info": None,
        "marketing_tag": None,
        "offer_headline": None,
        "offer_threshold": None,
        "earning_rates": None,
        "pricing_terms_url": None,
        "rewards_agreement_url": None,
    }

    # card_name
    try:
        name_link = card_el.query_selector("h2 a, h3 a")
        if name_link:
            txt = _text(name_link)
            if txt:
                txt = txt.replace("\nLinks to product page", "").replace("Links to product page", "")
                txt = txt.replace("\ncredit card", "").replace("\nCredit Card", "").replace("\nCREDIT CARD", "")
                txt = txt.replace("credit card", "").replace("Credit Card", "").replace("CREDIT CARD", "")
                txt = txt.replace("  ", " ").strip()
                if txt and txt.lower() not in ["credit card", "links to product page", ""]:
                    data["card_name"] = txt
    except Exception:
        pass

    # details_url
    try:
        link_el = card_el.query_selector("h2 a, h3 a, [data-pt-name*='_name']")
        if link_el:
            href = _href(link_el)
            if href and not href.startswith('#'):
                if not href.startswith('http'):
                    href = 'https://creditcards.chase.com' + href
                data["details_url"] = href
    except Exception:
        pass

    # annual_fee
    try:
        sections = card_el.query_selector_all("div, span, p, li")
        for sec in sections:
            txt = _text(sec)
            if txt and "annual fee" in txt.lower() and len(txt) < 200:
                data["annual_fee"] = txt
                break
    except Exception:
        pass

    # apr_info
    try:
        sections = card_el.query_selector_all("div, span, p, li")
        for sec in sections:
            txt = _text(sec)
            if txt and "apr" in txt.lower() and len(txt) > 10 and len(txt) < 500:
                data["apr_info"] = txt
                break
    except Exception:
        pass

    # marketing_tag
    try:
        tag_el = card_el.query_selector(
            "[class*='ribbon'], [class*='marketing-tag'], [class*='marketingTag'], "
            "[class*='limitedTime'], [class*='badge'], [class*='flag'], [class*='callout']"
        )
        data["marketing_tag"] = _text(tag_el)
    except Exception:
        pass

    # offer_headline
    try:
        headline_el = card_el.query_selector("[class*='cardHeader'] p, strong p")
        if headline_el:
            txt = _text(headline_el)
            if txt and ("bonus" in txt.lower() or "points" in txt.lower() or "$" in txt):
                data["offer_headline"] = txt
    except Exception:
        pass

    # offer_threshold
    try:
        sections = card_el.query_selector_all("p, div")
        for sec in sections:
            txt = _text(sec)
            if txt and "spend" in txt.lower() and ("purchase" in txt.lower() or "months" in txt.lower()) and len(txt) < 400 and len(txt) > 20:
                data["offer_threshold"] = txt
                break
    except Exception:
        pass

    # earning_rates (At A Glance)
    try:
        sections = card_el.query_selector_all("div, p")
        for sec in sections:
            txt = _text(sec)
            if txt and ("AT A GLANCE" in txt or "CARDMEMBER REWARDS" in txt):
                data["earning_rates"] = txt
                break
        if not data["earning_rates"]:
            for sec in sections:
                txt = _text(sec)
                if txt and (("x" in txt.lower() or "%" in txt) and ("earn" in txt.lower() or "cash back" in txt.lower()) and len(txt) > 30 and len(txt) < 600):
                    data["earning_rates"] = txt
                    break
    except Exception:
        pass

    # pricing_terms_url
    try:
        pt_el = card_el.query_selector(
            "a:has-text('Pricing & Terms'), a:has-text('Pricing and Terms'), a:has-text('pricing')"
        )
        if pt_el:
            href = _href(pt_el)
            if href and 'pricing' in href.lower():
                data["pricing_terms_url"] = href
    except Exception:
        pass

    # rewards_agreement_url
    try:
        # Look for RPA (Rewards Program Agreement) PDFs only
        # Pattern: https://asset.chase.com/.../RPA####_Web.pdf
        # Try multiple selectors
        ra_el = card_el.query_selector(
            "a:has-text('Rewards Program Agreement'), "
            "a:has-text('Rewards Agreement')"
        )
        
        # If not found by text, try href pattern
        if not ra_el:
            ra_el = card_el.query_selector("a[href*='RPA'][href$='.pdf']")
        
        if ra_el:
            href = _href(ra_el)
            # Validate: must be http URL ending in .pdf with 'RPA' in path
            if href and href.startswith('http') and '.pdf' in href.lower() and 'RPA' in href:
                # Reject Benefits Guide PDFs (BGC*.pdf)
                if 'BGC' not in href:
                    data["rewards_agreement_url"] = href
                else:
                    log.warning(f"  Rejected Benefits Guide PDF for {data.get('card_name', 'unknown')}")
            else:
                log.warning(f"  No valid RPA PDF found for {data.get('card_name', 'unknown')}")
        else:
            log.warning(f"  No rewards agreement anchor found for {data.get('card_name', 'unknown')}")
    except Exception as e:
        log.warning(f"  Error finding rewards URL for {data.get('card_name', 'unknown')}: {e}")

    return data


def run():
    log.info("Launching Playwright (headless Chromium)...")
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

        log.info("Navigating to %s", URL)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        # Wait for card containers to appear
        log.info("Waiting for card containers to render...")
        try:
            page.wait_for_selector(
                "[data-card-id]",
                timeout=30000,
            )
        except PwTimeout:
            log.warning("Primary selector timed out; trying fallback selector...")
            try:
                page.wait_for_selector("[class*='Grid-module']", timeout=15000)
            except PwTimeout:
                log.error("Could not find any card containers on the page.")
                browser.close()
                return []

        scroll_page(page)

        # Identify card containers (list view uses cmp-cardsummary__inner-container)
        cards_els = page.query_selector_all(".cmp-cardsummary__inner-container[data-card-id]")
        if not cards_els:
            log.warning("No cards found with list view selector; trying grid view fallback.")
            cards_els = page.query_selector_all("[data-card-id]")

        log.info("Found %d card container(s).", len(cards_els))

        results = []
        for idx, card_el in enumerate(cards_els, start=1):
            log.info("Extracting card %d/%d...", idx, len(cards_els))
            card_data = extract_card(card_el)
            if card_data["card_name"]:
                results.append(card_data)
                log.info("  -> %s", card_data["card_name"])
            else:
                log.warning("  -> Card %d: name not found, skipping.", idx)

        browser.close()

    log.info("Extraction complete. %d card(s) collected.", len(results))
    return results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cards = run()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)
    log.info("Results written to %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
