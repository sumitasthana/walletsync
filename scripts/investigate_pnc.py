"""
Investigate PNC credit card pages for multi-bank onboarding (spike).

Captures the card listing, comparison, and product pages, then follows the
pricing ("Rates and Fees") and rewards ("Rewards Terms and Conditions") links
so their formats can be inspected. Saves raw HTML under data/pnc/spike/ and
prints a findings summary. Read-only against PNC; no LLM calls.

Usage:
    python scripts/investigate_pnc.py
"""

import logging
import os
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

LISTING_URL = "https://www.pnc.com/en/personal-banking/banking/credit-cards.html"
COMPARISON_URL = "https://www.pnc.com/en/personal-banking/banking/credit-cards/credit-card-comparison.html"
SPIKE_DIR = os.path.join("data", "pnc", "spike")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Link text that points at pricing or rewards disclosure documents
PRICING_LINK_TEXTS = ("rates and fees", "pricing", "rates", "fee schedule")
REWARDS_LINK_TEXTS = ("rewards terms", "cash back terms", "program terms")


def slugify(url):
    """Turn a URL into a safe filename."""
    path = url.split("//", 1)[-1].split("?", 1)[0].strip("/").replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", path)[:100] or "page"


def fetch(page, url):
    """Navigate to a URL and return the rendered HTML, or None on failure."""
    log.info(f"Fetching: {url}")
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        status = resp.status if resp else None
        if status and status >= 400:
            log.warning(f"  HTTP {status} for {url}")
        html = page.content()
        if len(html) < 2000:
            log.warning(f"  Suspiciously short content ({len(html)} bytes)")
        return html
    except Exception as e:
        log.error(f"  Failed: {e}")
        return None


def save(name, html):
    """Save HTML into the spike dir; return the file path."""
    os.makedirs(SPIKE_DIR, exist_ok=True)
    path = os.path.join(SPIKE_DIR, f"{name}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info(f"  Saved: {path} ({len(html)} bytes)")
    return path


def extract_links(html, base_url):
    """Return (text, href) pairs for all links, resolved against base_url."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(base_url, a["href"])
        if text:
            links.append((text, href))
    return links


def find_document_links(links):
    """Classify links that look like pricing or rewards disclosures."""
    pricing, rewards, pdfs = [], [], []
    for text, href in links:
        low = text.lower()
        if href.lower().endswith(".pdf") or ".pdf?" in href.lower():
            pdfs.append((text, href))
        if any(p in low for p in PRICING_LINK_TEXTS):
            pricing.append((text, href))
        if any(r in low for r in REWARDS_LINK_TEXTS):
            rewards.append((text, href))
    return pricing, rewards, pdfs


def find_product_links(links):
    """Find product detail page links from listing/comparison page links."""
    seen = set()
    products = []
    for text, href in links:
        if "/credit-cards/" not in href:
            continue
        if href.rstrip("/") in (LISTING_URL.rstrip("/"), COMPARISON_URL.rstrip("/")):
            continue
        if href in seen:
            continue
        # Product pages live deeper than the section pages
        remainder = href.split("/credit-cards/", 1)[1].rstrip("/")
        if remainder and "/" not in remainder:
            continue  # section nav like /credit-cards.html or comparison
        seen.add(href)
        products.append((text, href))
    return products


def summarize_tables(html):
    """Count HTML tables and report their largest row labels (Schumer hint)."""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    best = []
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) >= 3:
            labels = []
            for tr in rows[:6]:
                cells = tr.find_all(["td", "th"])
                if cells:
                    labels.append(cells[0].get_text(" ", strip=True)[:40])
            best.append((len(rows), labels))
    return len(tables), best


def main():
    findings = {"pages": [], "pricing_links": [], "rewards_links": [], "pdf_links": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
        )
        page = context.new_page()

        products = []

        # 1. Listing page
        html = fetch(page, LISTING_URL)
        if html:
            save("listing", html)
            findings["pages"].append(("listing", LISTING_URL, len(html)))
            links = extract_links(html, LISTING_URL)
            pricing, rewards, pdfs = find_document_links(links)
            findings["pricing_links"] += pricing
            findings["rewards_links"] += rewards
            findings["pdf_links"] += pdfs
            products = find_product_links(links)
            log.info(f"  Product links found on listing: {len(products)}")

        # 2. Comparison page
        html = fetch(page, COMPARISON_URL)
        if html:
            save("comparison", html)
            findings["pages"].append(("comparison", COMPARISON_URL, len(html)))
            links = extract_links(html, COMPARISON_URL)
            pricing, rewards, pdfs = find_document_links(links)
            findings["pricing_links"] += pricing
            findings["rewards_links"] += rewards
            findings["pdf_links"] += pdfs
            if not products:
                products = find_product_links(links)
                log.info(f"  Product links found on comparison: {len(products)}")

        # 3. Product pages (up to 6)
        product_pages = []
        for text, href in products[:6]:
            html = fetch(page, href)
            if not html:
                continue
            name = "product_" + slugify(href)
            save(name, html)
            product_pages.append((text, href))
            findings["pages"].append((f"product: {text}", href, len(html)))
            links = extract_links(html, href)
            pricing, rewards, pdfs = find_document_links(links)
            findings["pricing_links"] += pricing
            findings["rewards_links"] += rewards
            findings["pdf_links"] += pdfs

        # 4. Follow up to 3 pricing links and 2 rewards links
        seen_docs = set()
        docs_to_fetch = (findings["pricing_links"][:3] + findings["rewards_links"][:2])
        for text, href in docs_to_fetch:
            if href in seen_docs:
                continue
            seen_docs.add(href)
            html = fetch(page, href)
            if not html:
                continue
            name = "doc_" + slugify(href)
            save(name, html)
            findings["pages"].append((f"doc: {text}", href, len(html)))
            if href.lower().split("?")[0].endswith(".pdf"):
                log.info("  (PDF link: format check needed offline)")

        browser.close()

    # Summary
    log.info("\n" + "=" * 80)
    log.info("PNC SPIKE SUMMARY")
    log.info("=" * 80)
    log.info(f"Pages captured: {len(findings['pages'])}")
    for label, url, size in findings["pages"]:
        log.info(f"  {label}: {url} ({size} bytes)")
    log.info(f"\nPricing links found: {len(findings['pricing_links'])}")
    for text, href in findings["pricing_links"][:10]:
        log.info(f"  [{text}] {href}")
    log.info(f"\nRewards links found: {len(findings['rewards_links'])}")
    for text, href in findings["rewards_links"][:10]:
        log.info(f"  [{text}] {href}")
    log.info(f"\nPDF links found: {len(findings['pdf_links'])}")
    for text, href in findings["pdf_links"][:10]:
        log.info(f"  [{text}] {href}")
    log.info(f"\nRaw captures saved under: {SPIKE_DIR}")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
