#!/usr/bin/env python
"""
WalletSync Card Data Extractor

CLI application to extract comprehensive credit card data from Chase card pages.

Usage:
    python extract_card_data.py --url <chase_card_url>
    python extract_card_data.py --card-id <card_id>
    python extract_card_data.py --batch <num_cards>
    python extract_card_data.py --list

Examples:
    # Extract single card by URL
    python extract_card_data.py --url "https://creditcards.chase.com/cash-back-credit-cards/freedom/flex"
    
    # Extract single card by ID (from cleaned data)
    python extract_card_data.py --card-id freedom-flex-a6950e
    
    # Extract first N cards
    python extract_card_data.py --batch 5
    
    # List available cards
    python extract_card_data.py --list

Output:
    - data/cards/<card_id>.json - Complete card data (pricing + rewards merged)
    - data/extracted_pricing_extended.json - All pricing data
    - data/extracted_rewards_extended.json - All rewards data
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def load_cleaned_cards() -> List[Dict]:
    """Load cleaned card data."""
    cleaned_path = Path('data/chase_cards_clean.json')
    if not cleaned_path.exists():
        log.error("Cleaned card data not found. Run src/scraper/clean_data.py first.")
        sys.exit(1)
    
    with open(cleaned_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_available_cards():
    """List all available cards."""
    cards = load_cleaned_cards()
    
    print("\n" + "="*80)
    print("AVAILABLE CARDS")
    print("="*80)
    
    for idx, card in enumerate(cards, 1):
        card_id = card.get('card_id', 'unknown')
        card_name = card.get('card_name', 'Unknown')
        has_pricing = bool(card.get('pricing_terms_url'))
        has_rewards = bool(card.get('rewards_agreement_url'))
        
        status = []
        if has_pricing:
            status.append("pricing")
        if has_rewards:
            status.append("rewards")
        
        status_str = f"[{', '.join(status)}]" if status else "[no URLs]"
        
        print(f"{idx:3d}. {card_id:30s} {card_name:40s} {status_str}")
    
    print(f"\nTotal: {len(cards)} cards")
    print("="*80 + "\n")


def find_card_by_id(card_id: str) -> Optional[Dict]:
    """Find card by card_id."""
    cards = load_cleaned_cards()
    for card in cards:
        if card.get('card_id') == card_id:
            return card
    return None


def extract_dumps(card_ids: List[str], force: bool = False):
    """Extract raw dumps (pricing + rewards) for specified cards."""
    import subprocess
    
    log.info(f"Extracting dumps for {len(card_ids)} cards...")
    
    # Run dump_pricing_text.py
    log.info("Dumping pricing pages...")
    cmd = ['python', 'src/pricing/dump_pricing_text.py']
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Pricing dump failed: {result.stderr}")
        return False
    
    # Run dump_rewards_text.py
    log.info("Dumping rewards PDFs...")
    cmd = ['python', 'src/rewards/dump_rewards_text.py']
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Rewards dump failed: {result.stderr}")
        return False
    
    return True


def extract_structured_data(card_ids: List[str], force: bool = False):
    """Extract structured data (pricing + rewards) for specified cards."""
    import subprocess
    
    log.info(f"Extracting structured data for {len(card_ids)} cards...")
    
    # Run extract_pricing_extended.py
    log.info("Extracting pricing data...")
    cmd = ['python', 'src/pricing/parse_pricing_deterministic.py']
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Pricing extraction failed: {result.stderr}")
        return False
    
    # Run extract_rewards_extended.py
    log.info("Extracting rewards data...")
    cmd = ['python', 'src/rewards/extract_rewards_extended.py']
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Rewards extraction failed: {result.stderr}")
        return False
    
    return True


def merge_card_data(card_id: str) -> Optional[Dict]:
    """Merge pricing and rewards data for a single card."""
    # Load pricing data
    pricing_path = Path('data/extracted_pricing_extended.json')
    pricing_data = None
    if pricing_path.exists():
        with open(pricing_path, 'r', encoding='utf-8') as f:
            all_pricing = json.load(f)
            # Skip metadata record
            pricing_records = [p for p in all_pricing if '_meta' not in p]
            for p in pricing_records:
                if p.get('card_id') == card_id:
                    pricing_data = p
                    break
    
    # Load rewards data
    rewards_path = Path('data/extracted_rewards_extended.json')
    rewards_data = None
    if rewards_path.exists():
        with open(rewards_path, 'r', encoding='utf-8') as f:
            all_rewards = json.load(f)
            # Skip metadata record
            rewards_records = [r for r in all_rewards if '_meta' not in r]
            for r in rewards_records:
                if r.get('card_id') == card_id:
                    rewards_data = r
                    break
    
    # Load base card data
    card = find_card_by_id(card_id)
    if not card:
        return None
    
    # Merge all data
    merged = {
        '_meta': {
            'card_id': card_id,
            'extracted_at': datetime.now(timezone.utc).isoformat(),
            'data_sources': []
        },
        'card_info': {
            'card_id': card.get('card_id'),
            'card_name': card.get('card_name'),
            'annual_fee_usd': card.get('annual_fee_usd'),
            'waived_first_year': card.get('waived_first_year'),
            'reward_currency': card.get('reward_currency'),
            'sign_up_bonus_value': card.get('sign_up_bonus_value'),
            'sign_up_bonus_spend_req': card.get('sign_up_bonus_spend_req'),
            'sign_up_bonus_months': card.get('sign_up_bonus_months'),
            'base_earn_rate': card.get('base_earn_rate'),
            'pricing_terms_url': card.get('pricing_terms_url'),
            'rewards_agreement_url': card.get('rewards_agreement_url')
        }
    }
    
    if pricing_data:
        merged['pricing'] = pricing_data
        merged['_meta']['data_sources'].append('pricing_extended')
    
    if rewards_data:
        merged['rewards'] = rewards_data
        merged['_meta']['data_sources'].append('rewards_extended')
    
    return merged


def save_individual_card(card_id: str, data: Dict):
    """Save individual card data to data/cards/<card_id>.json"""
    cards_dir = Path('data/cards')
    cards_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = cards_dir / f"{card_id}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    log.info(f"✓ Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract comprehensive credit card data from Chase',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--url', help='Chase card URL to extract')
    input_group.add_argument('--card-id', help='Card ID from cleaned data')
    input_group.add_argument('--batch', type=int, metavar='N', help='Extract first N cards')
    input_group.add_argument('--list', action='store_true', help='List available cards')
    
    # Options
    parser.add_argument('--force', action='store_true', help='Force re-extraction even if data exists')
    parser.add_argument('--skip-dumps', action='store_true', help='Skip dump step (use existing dumps)')
    parser.add_argument('--output-dir', default='data/cards', help='Output directory for individual card JSONs')
    
    args = parser.parse_args()
    
    # Handle --list
    if args.list:
        list_available_cards()
        return
    
    # Determine which cards to extract
    card_ids = []
    
    if args.card_id:
        card = find_card_by_id(args.card_id)
        if not card:
            log.error(f"Card ID not found: {args.card_id}")
            log.info("Use --list to see available cards")
            sys.exit(1)
        card_ids = [args.card_id]
    
    elif args.batch:
        cards = load_cleaned_cards()
        # Get first N cards that have at least one URL
        for card in cards[:args.batch]:
            if card.get('pricing_terms_url') or card.get('rewards_agreement_url'):
                card_ids.append(card['card_id'])
        
        if not card_ids:
            log.error("No cards with URLs found in batch")
            sys.exit(1)
    
    elif args.url:
        log.error("URL-based extraction not yet implemented")
        log.info("Use --card-id or --batch instead")
        sys.exit(1)
    
    # Execute extraction pipeline
    log.info(f"\n{'='*80}")
    log.info(f"EXTRACTION PIPELINE")
    log.info(f"{'='*80}")
    log.info(f"Cards to extract: {len(card_ids)}")
    log.info(f"Card IDs: {', '.join(card_ids)}")
    log.info(f"{'='*80}\n")
    
    # Step 1: Extract dumps (unless skipped)
    if not args.skip_dumps:
        log.info("STEP 1: Extracting raw dumps...")
        if not extract_dumps(card_ids, args.force):
            log.error("Dump extraction failed")
            sys.exit(1)
    else:
        log.info("STEP 1: Skipped (using existing dumps)")
    
    # Step 2: Extract structured data
    log.info("\nSTEP 2: Extracting structured data...")
    if not extract_structured_data(card_ids, args.force):
        log.error("Structured extraction failed")
        sys.exit(1)
    
    # Step 3: Merge and save individual card files
    log.info("\nSTEP 3: Merging and saving individual card files...")
    success_count = 0
    
    for card_id in card_ids:
        merged_data = merge_card_data(card_id)
        if merged_data:
            save_individual_card(card_id, merged_data)
            success_count += 1
        else:
            log.warning(f"✗ Failed to merge data for {card_id}")
    
    # Summary
    log.info(f"\n{'='*80}")
    log.info(f"EXTRACTION COMPLETE")
    log.info(f"{'='*80}")
    log.info(f"✓ Successfully extracted: {success_count}/{len(card_ids)} cards")
    log.info(f"✓ Individual card files: data/cards/")
    log.info(f"✓ Combined pricing data: data/extracted_pricing_extended.json")
    log.info(f"✓ Combined rewards data: data/extracted_rewards_extended.json")
    log.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()
