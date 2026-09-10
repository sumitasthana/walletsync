"""Deterministic pricing parser - no LLM, pure regex on structured Schumer Box data."""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.banks import get_bank
from src.common.schemas import PricingExtended

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def find_row(rows: dict, *patterns: str) -> Optional[str]:
    """
    Find first row whose label contains any of the patterns (case-insensitive).
    
    Args:
        rows: Dict of label → value from Schumer Box
        patterns: One or more patterns to search for
        
    Returns:
        Row value if found, None otherwise
    """
    for label, value in rows.items():
        lower = label.lower()
        for p in patterns:
            if p.lower() in lower:
                return value
    return None


def parse_apr_range(text: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """
    Parse APR range like '18.24% to 27.74%' or single APR like '25.24%'.
    
    Args:
        text: Text containing APR range or single APR
        
    Returns:
        Tuple of (min_apr, max_apr) or (apr, apr) for single values, or (None, None) if not found
    """
    if not text:
        return (None, None)
    
    # Try range first
    m = re.search(r'(\d+\.\d+)\s*%\s*(?:to|–|-|—)\s*(\d+\.\d+)\s*%', text)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    
    # Try single APR (e.g., "25.24%")
    m = re.search(r'(\d+\.\d+)\s*%', text)
    if m:
        apr = float(m.group(1))
        return (apr, apr)
    
    return (None, None)


def parse_intro_apr(text: Optional[str]) -> tuple[Optional[float], Optional[int]]:
    """
    Parse intro APR like '0% Intro APR for 15 months' or '0% Promo APR for six months' → (0.0, 15).
    
    Args:
        text: Text containing intro APR offer
        
    Returns:
        Tuple of (intro_pct, intro_months) or (None, None) if not found
    """
    if not text:
        return (None, None)
    
    # Word to number mapping for months
    word_to_num = {
        'six': 6, 'twelve': 12, 'fifteen': 15, 'eighteen': 18,
        'twenty-four': 24, 'twenty four': 24
    }
    
    # Try numeric months first: "0% Intro APR for 15 months"
    m = re.search(r'(\d+(?:\.\d+)?)\s*%\s+(?:fixed\s+)?(?:intro|promo)\s+apr\s+for\s+(?:the\s+first\s+)?(\d+)\s+months?', text, re.IGNORECASE)
    if m:
        return (float(m.group(1)), int(m.group(2)))
    
    # Try word months: "0% Promo APR for the first six months"
    m = re.search(r'(\d+(?:\.\d+)?)\s*%\s+(?:fixed\s+)?(?:intro|promo)\s+apr\s+for\s+(?:the\s+first\s+)?(\w+)\s+months?', text, re.IGNORECASE)
    if m:
        word = m.group(2).lower()
        if word in word_to_num:
            return (float(m.group(1)), word_to_num[word])
    
    return (None, None)


def parse_single_apr(text: Optional[str]) -> Optional[float]:
    """
    Parse single APR like '28.49%' → 28.49. Handles 'Up to 29.99%' and plain '28.49%'.
    
    Args:
        text: Text containing APR percentage
        
    Returns:
        APR as float or None if not found
    """
    if not text:
        return None
    m = re.search(r'(\d+\.\d+)\s*%', text)
    return float(m.group(1)) if m else None


def parse_dollar_fee(text: Optional[str]) -> Optional[int]:
    """
    Parse dollar fee like 'Up to $40.' → 40. '$10 or 5%' → 10.
    
    Args:
        text: Text containing dollar amount
        
    Returns:
        Fee amount as int or None if not found
    """
    if not text:
        return None
    m = re.search(r'\$(\d+)', text)
    return int(m.group(1)) if m else None


def parse_percent(text: Optional[str]) -> Optional[float]:
    """
    Parse percentage like '3% of each transaction' → 3.0.
    
    Args:
        text: Text containing percentage
        
    Returns:
        Percentage as float or None if not found
    """
    if not text:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
    return float(m.group(1)) if m else None


def parse_bt_window_days(text: Optional[str]) -> Optional[int]:
    """
    Parse balance transfer window like 'transfer within 60 days' → 60.
    
    Args:
        text: Text containing BT window (usually full_page_text)
        
    Returns:
        Days as int or None if not found
    """
    if not text:
        return None
    m = re.search(r'within\s+(\d+)\s+days', text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_apr_index(text: Optional[str]) -> Optional[str]:
    """
    Parse APR index like 'based on the Prime Rate' → 'Prime Rate'.
    
    Args:
        text: Text containing APR index reference
        
    Returns:
        Index name or None if not found
    """
    if not text:
        return None
    if re.search(r'prime\s+rate', text, re.IGNORECASE):
        return "Prime Rate"
    return None


def parse_apr_margin(text: Optional[str]) -> Optional[float]:
    """
    Parse APR margin like 'Prime Rate + 13.99%' → 13.99.
    
    Args:
        text: Text containing margin over index
        
    Returns:
        Margin as float or None if not found
    """
    if not text:
        return None
    # Look for "Prime Rate + X%" or "add X% to the Prime Rate"
    m = re.search(r'(?:prime\s+rate\s*\+\s*|add\s+)(\d+\.\d+)\s*%', text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def parse_fee_structure(text: Optional[str]) -> tuple[Optional[float], Optional[int], Optional[int]]:
    """
    Parse fee structure like 'Either $5 or 5% of the amount, whichever is greater' → (5.0, 5, None).
    
    Args:
        text: Text containing fee structure
        
    Returns:
        Tuple of (pct, min_usd, max_usd)
    """
    if not text:
        return (None, None, None)
    
    pct = None
    min_usd = None
    max_usd = None
    
    # Extract percentage
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
    if pct_match:
        pct = float(pct_match.group(1))
    
    # Extract dollar amounts
    dollar_matches = re.findall(r'\$(\d+)', text)
    if dollar_matches:
        min_usd = int(dollar_matches[0])
        if len(dollar_matches) > 1:
            max_usd = int(dollar_matches[1])
    
    return (pct, min_usd, max_usd)


def parse_pricing(dump: dict) -> PricingExtended:
    """
    Parse pricing dump into PricingExtended record using deterministic regex.
    
    Args:
        dump: JSON dump from dump_pricing_text.py
        
    Returns:
        Validated PricingExtended record
    """
    rows = dump["schumer_rows"]
    full_text = dump.get("full_page_text", "")
    
    # Purchase APR (or "Flex for Business APR" for business cards)
    purchase_row = find_row(rows, "Purchase Annual Percentage Rate", "APR for Purchases", "Purchases APR", "Flex for Business")
    apr_min, apr_max = parse_apr_range(purchase_row)
    intro_pct, intro_months = parse_intro_apr(purchase_row)
    
    # Balance Transfer APR
    bt_row = find_row(rows, "Balance Transfer APR", "APR for Balance Transfers")
    bt_apr_min, bt_apr_max = parse_apr_range(bt_row)
    bt_intro_pct, bt_intro_months = parse_intro_apr(bt_row)
    
    # BT window (usually in footnotes of full_page_text, not Schumer Box)
    bt_window = parse_bt_window_days(full_text) if bt_intro_months else None
    
    # Cash Advance APR - look for row with "Cash Advance APR" specifically
    ca_apr_row = find_row(rows, "Cash Advance APR")
    ca_apr = parse_single_apr(ca_apr_row)
    
    # If no Cash Advance APR found, check for business card "Flex for Business APR"
    if ca_apr is None:
        flex_row = find_row(rows, "Flex for Business")
        if flex_row:
            # Use max of range as cash advance APR for business cards
            _, flex_max = parse_apr_range(flex_row)
            ca_apr = flex_max
    
    # Penalty APR (or "Default APR" for business cards)
    pen_apr_row = find_row(rows, "Penalty APR", "Default APR")
    pen_apr = parse_single_apr(pen_apr_row)
    
    # Foreign transaction fee
    ft_row = find_row(rows, "Foreign Transaction")
    ft_pct = parse_percent(ft_row)
    
    # Handle "None" as 0%
    if ft_row and re.search(r'\bnone\b', ft_row, re.IGNORECASE):
        ft_pct = 0.0
    
    # Late payment fee
    late_row = find_row(rows, "Late Payment")
    late_fee = parse_dollar_fee(late_row)
    
    # Cash Advance fee - disambiguate from APR row
    ca_fee_row = None
    for label, value in rows.items():
        if "cash advance" in label.lower() and "apr" not in label.lower():
            ca_fee_row = value
            break
    ca_fee_pct, ca_fee_min, _ = parse_fee_structure(ca_fee_row)
    
    # Balance Transfer fee - disambiguate from APR row
    bt_fee_row = None
    for label, value in rows.items():
        if "balance transfer" in label.lower() and "apr" not in label.lower():
            bt_fee_row = value
            break
    bt_fee_pct, bt_fee_min, bt_fee_max = parse_fee_structure(bt_fee_row)
    
    # APR index and margin
    apr_index = parse_apr_index(purchase_row or full_text)
    apr_margin = parse_apr_margin(full_text)
    
    # Authorized user fee (search full_text)
    au_fee = None
    m = re.search(r'\$(\d+)\s+for\s+each\s+authorized\s+user', full_text, re.IGNORECASE)
    if m:
        au_fee = int(m.group(1))
    
    # Check for "None" or "$0" in authorized user context
    if re.search(r'authorized\s+user.*?(?:none|\$0)', full_text, re.IGNORECASE):
        au_fee = 0
    
    return PricingExtended(
        card_id=dump["card_id"],
        card_name=dump["card_name"],
        pricing_terms_url=dump["pricing_terms_url"],
        purchase_apr_min=apr_min,
        purchase_apr_max=apr_max,
        purchase_apr_intro_pct=intro_pct,
        purchase_apr_intro_months=intro_months,
        bt_apr_min=bt_apr_min,
        bt_apr_max=bt_apr_max,
        bt_apr_intro_pct=bt_intro_pct,
        bt_apr_intro_months=bt_intro_months,
        bt_intro_window_days=bt_window,
        cash_advance_apr=ca_apr,
        penalty_apr_max=pen_apr,
        foreign_transaction_fee_pct=ft_pct,
        balance_transfer_fee_pct=bt_fee_pct,
        balance_transfer_fee_min_usd=bt_fee_min,
        balance_transfer_fee_max_usd=bt_fee_max,
        cash_advance_fee_pct=ca_fee_pct,
        cash_advance_fee_min_usd=ca_fee_min,
        late_payment_fee_max_usd=late_fee,
        authorized_user_fee_usd=au_fee,
        apr_index=apr_index,
        purchase_apr_margin=apr_margin,
        apr_disclosure_date=None,
    )


def main():
    """Main execution - parse all pricing dumps."""
    parser = argparse.ArgumentParser(description="Parse pricing dumps deterministically")
    parser.add_argument('--bank', default='chase', help='Bank key (see src/banks/)')
    parser.add_argument('--force', action='store_true', help='Accepted for CLI compatibility; parsing always reprocesses all dumps')
    parser.add_argument('--limit', type=int, help='Limit number of dumps to process (for debugging)')
    args = parser.parse_args()

    bank = get_bank(args.bank)
    dump_dir = bank.raw_pricing_dir
    output_path = bank.extracted_pricing_path
    failures_path = bank.data_dir / "pricing_parse_failures.json"
    
    log.info(f"Loading dumps from {dump_dir}")
    
    results = []
    failures = []
    
    dump_paths = sorted(dump_dir.glob("*.json"))
    if args.limit:
        dump_paths = dump_paths[:args.limit]

    for dump_path in dump_paths:
        card_id = dump_path.stem
        log.info(f"Parsing {card_id}...")
        
        try:
            dump = json.load(open(dump_path, encoding='utf-8'))
            record = parse_pricing(dump)
            results.append(record.model_dump(mode='json'))
            log.info(f"  ✓ Parsed successfully")
        except Exception as e:
            log.error(f"  ✗ Failed: {e}")
            failures.append({"card_id": card_id, "error": str(e)})
    
    # Write results
    log.info(f"\nWriting results to {output_path}")
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Write failures if any
    if failures:
        log.warning(f"Writing {len(failures)} failures to {failures_path}")
        with open(failures_path, "w", encoding='utf-8') as f:
            json.dump(failures, f, indent=2, ensure_ascii=False)
    
    # Summary
    log.info(f"\n{'='*80}")
    log.info(f"SUMMARY")
    log.info(f"{'='*80}")
    log.info(f"✓ Parsed: {len(results)}/{len(results)+len(failures)}")
    log.info(f"✗ Failed: {len(failures)}")
    log.info(f"Output: {output_path}")
    
    if failures:
        log.warning(f"\nFailed cards:")
        for f in failures:
            log.warning(f"  - {f['card_id']}: {f['error']}")


if __name__ == '__main__':
    main()
