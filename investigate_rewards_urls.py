"""
Investigate rewards PDF URLs for cards with missing/broken URLs.
"""
import json
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Cards to investigate
CARDS_TO_CHECK = [
    "Chase Sapphire Reserve®",
    "Chase Sapphire Preferred®",
    "IHG One Rewards Premier",
    "IHG One Rewards Traveler",
    "Disney® Inspire Visa® Card",
    "Disney® Premier Visa® Card",
    "Disney® Visa® Card",
    "Prime Visa",
    "Amazon Visa",
    "Slate®"
]

def investigate_card(page, card_name, details_url):
    """Investigate a single card's rewards URL."""
    result = {
        "card_name": card_name,
        "details_url": details_url,
        "pdf_anchor_found": False,
        "anchor_text": None,
        "pdf_href": None,
        "inline_html_rewards": False,
        "all_pdf_links": [],
        "all_reward_anchors": [],
        "verdict": None
    }
    
    try:
        log.info(f"\nInvestigating: {card_name}")
        log.info(f"URL: {details_url}")
        
        page.goto(details_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)  # Extra wait for JS
        
        # Find ALL anchors with PDF hrefs
        pdf_anchors = page.query_selector_all("a[href*='.pdf']")
        for anchor in pdf_anchors:
            href = anchor.get_attribute("href") or ""
            text = anchor.inner_text().strip()
            if href:
                result["all_pdf_links"].append({
                    "text": text,
                    "href": href
                })
                log.info(f"  Found PDF link: '{text}' -> {href}")
        
        # Find anchors with "reward" in text or href
        reward_anchors = page.query_selector_all("a")
        for anchor in reward_anchors:
            href = anchor.get_attribute("href") or ""
            text = anchor.inner_text().strip()
            if text and ("reward" in text.lower() or "agreement" in text.lower() or "program" in text.lower()):
                if len(text) < 100:  # Skip large text blocks
                    result["all_reward_anchors"].append({
                        "text": text,
                        "href": href
                    })
        
        # Check for specific rewards agreement PDF
        rewards_pdf_selectors = [
            "a:has-text('Rewards Program Agreement')",
            "a:has-text('Rewards Agreement')",
            "a:has-text('Ultimate Rewards')",
            "a:has-text('Rewards Terms')",
            "a:has-text('Program Rules')",
            "a:has-text('Rewards Program Terms')",
            "a[href*='RPA']",
            "a[href*='rewards'][href*='.pdf']",
            "a[href*='agreement'][href*='.pdf']"
        ]
        
        for selector in rewards_pdf_selectors:
            try:
                anchor = page.query_selector(selector)
                if anchor:
                    href = anchor.get_attribute("href") or ""
                    text = anchor.inner_text().strip()
                    if href and ".pdf" in href.lower():
                        result["pdf_anchor_found"] = True
                        result["anchor_text"] = text
                        result["pdf_href"] = href
                        log.info(f"  ✓ Rewards PDF found via '{selector}'")
                        log.info(f"    Text: '{text}'")
                        log.info(f"    Href: {href}")
                        break
            except:
                pass
        
        # Check for inline rewards section
        inline_selectors = [
            "text='Rewards Program Details'",
            "text='How You Earn'",
            "text='Earning Rewards'",
            "text='Redemption Options'"
        ]
        for selector in inline_selectors:
            if page.query_selector(selector):
                result["inline_html_rewards"] = True
                log.info(f"  Found inline rewards section: {selector}")
                break
        
        # Determine verdict
        if result["pdf_anchor_found"]:
            result["verdict"] = "recoverable (scenario A)"
        elif len(result["all_pdf_links"]) > 0:
            result["verdict"] = "recoverable (scenario A) - PDF exists but needs better selector"
        elif result["inline_html_rewards"]:
            result["verdict"] = "no PDF exists (scenario C) - inline HTML only"
        else:
            # Check page source for hidden PDF links
            content = page.content()
            if ".pdf" in content and "reward" in content.lower():
                result["verdict"] = "JS-loaded (scenario B) - PDF in source but not rendered"
            else:
                result["verdict"] = "no PDF exists (scenario C)"
        
        log.info(f"  Verdict: {result['verdict']}")
        
    except Exception as e:
        log.error(f"  Error investigating {card_name}: {e}")
        result["verdict"] = "error - could not load page"
    
    return result


def main():
    # Load cards
    with open("output/chase_cards_clean.json", "r", encoding="utf-8") as f:
        cards = json.load(f)
    
    # Find cards to investigate
    cards_to_check = []
    for card in cards:
        if card.get("card_name") in CARDS_TO_CHECK:
            cards_to_check.append(card)
    
    log.info(f"Found {len(cards_to_check)} cards to investigate")
    
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Use headless=False to see what's happening
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        
        for card in cards_to_check:
            # Try to get details_url from raw data
            with open("output/chase_cards.json", "r", encoding="utf-8") as f:
                raw_cards = json.load(f)
            
            details_url = None
            for raw_card in raw_cards:
                if raw_card.get("card_name") == card.get("card_name"):
                    details_url = raw_card.get("details_url")
                    break
            
            if not details_url:
                log.warning(f"No details_url found for {card.get('card_name')}")
                continue
            
            result = investigate_card(page, card.get("card_name"), details_url)
            results.append(result)
        
        browser.close()
    
    # Write markdown report
    with open("output/rewards_url_investigation.md", "w", encoding="utf-8") as f:
        f.write("# Rewards URL Investigation\n\n")
        f.write("Investigation of 10 cards with missing/broken rewards PDF URLs.\n\n")
        f.write("---\n\n")
        
        for result in results:
            f.write(f"## {result['card_name']}\n\n")
            f.write(f"**details_url:** {result['details_url']}\n\n")
            f.write(f"**PDF anchor found:** {'YES' if result['pdf_anchor_found'] else 'NO'}\n\n")
            
            if result['pdf_anchor_found']:
                f.write(f"**Anchor text:** \"{result['anchor_text']}\"\n\n")
                f.write(f"**PDF href:** {result['pdf_href']}\n\n")
            
            f.write(f"**Inline HTML rewards section:** {'YES' if result['inline_html_rewards'] else 'NO'}\n\n")
            
            if result['all_pdf_links']:
                f.write(f"**All PDF links found ({len(result['all_pdf_links'])}):**\n\n")
                for link in result['all_pdf_links']:
                    f.write(f"- \"{link['text']}\" → {link['href']}\n")
                f.write("\n")
            
            if result['all_reward_anchors'][:5]:  # Show first 5
                f.write(f"**Reward-related anchors (sample):**\n\n")
                for anchor in result['all_reward_anchors'][:5]:
                    f.write(f"- \"{anchor['text']}\" → {anchor['href']}\n")
                f.write("\n")
            
            f.write(f"**Verdict:** {result['verdict']}\n\n")
            f.write("---\n\n")
        
        # Summary
        f.write("## Summary\n\n")
        scenario_a = sum(1 for r in results if "scenario A" in r['verdict'])
        scenario_b = sum(1 for r in results if "scenario B" in r['verdict'])
        scenario_c = sum(1 for r in results if "scenario C" in r['verdict'])
        errors = sum(1 for r in results if "error" in r['verdict'])
        
        f.write(f"- **Scenario A (recoverable with text pattern):** {scenario_a} cards\n")
        f.write(f"- **Scenario B (JS loaded):** {scenario_b} cards\n")
        f.write(f"- **Scenario C (no PDF exists):** {scenario_c} cards\n")
        f.write(f"- **Errors:** {errors} cards\n")
        f.write(f"- **Total:** {len(results)} cards\n\n")
    
    log.info(f"\n✓ Investigation complete. Report saved to output/rewards_url_investigation.md")
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    scenario_a = sum(1 for r in results if "scenario A" in r['verdict'])
    scenario_b = sum(1 for r in results if "scenario B" in r['verdict'])
    scenario_c = sum(1 for r in results if "scenario C" in r['verdict'])
    errors = sum(1 for r in results if "error" in r['verdict'])
    
    print(f"Scenario A (recoverable): {scenario_a} cards")
    print(f"Scenario B (JS loaded): {scenario_b} cards")
    print(f"Scenario C (no PDF exists): {scenario_c} cards")
    print(f"Errors: {errors} cards")
    print(f"Total: {len(results)} cards")
    print("="*80)


if __name__ == "__main__":
    main()
