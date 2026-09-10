#!/usr/bin/env python
"""
WalletSync Card Data Extractor

CLI application to extract comprehensive credit card data from supported
bank card pages (default: Chase).

Usage:
    python extract_card_data.py --url <card_url>
    python extract_card_data.py --card-id <card_id>
    python extract_card_data.py --batch <num_cards>
    python extract_card_data.py --list
    python extract_card_data.py --list-banks

Examples:
    # List supported banks
    python extract_card_data.py --list-banks

    # List available Chase cards (default bank)
    python extract_card_data.py --list

    # Extract first N cards
    python extract_card_data.py --bank chase --batch 5

    # Extract single card by ID (from cleaned data)
    python extract_card_data.py --card-id freedom-flex-a6950e

Output (under data/<bank>/):
    - cards/<card_id>.json - Complete card data (pricing + rewards merged)
    - extracted_pricing_extended.json - All pricing data
    - extracted_rewards_extended.json - All rewards data
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict

# Add project root to path so src.* imports resolve from any cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.banks import BANKS, get_bank
from src.common import merge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def load_cleaned_cards(bank) -> List[Dict]:
    """Load cleaned card data for a bank."""
    cleaned_path = bank.cards_clean_path
    if not cleaned_path.exists():
        log.error(f"Cleaned card data not found for bank '{bank.key}'. Run src/scraper/clean_data.py --bank {bank.key} first.")
        sys.exit(1)
    
    with open(cleaned_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_banks():
    """List all supported banks."""
    print("\n" + "="*80)
    print("SUPPORTED BANKS")
    print("="*80)
    
    for key in sorted(BANKS):
        bank = BANKS[key]
        if bank.cards_clean_path.exists():
            with open(bank.cards_clean_path, 'r', encoding='utf-8') as f:
                count = len(json.load(f))
        else:
            count = 0
        print(f"  {bank.key:10s} {bank.display_name:20s} [{bank.status}] {count} cards")
    
    print("="*80 + "\n")


def list_available_cards(bank):
    """List all available cards for a bank."""
    cards = load_cleaned_cards(bank)
    
    print("\n" + "="*80)
    print(f"AVAILABLE CARDS - {bank.display_name}")
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


def find_card_by_id(card_id: str, bank) -> Optional[Dict]:
    """Find card by card_id within a bank."""
    cards = load_cleaned_cards(bank)
    for card in cards:
        if card.get('card_id') == card_id:
            return card
    return None


def extract_dumps(card_ids: List[str], bank, force: bool = False):
    """Extract raw dumps (pricing + rewards) for specified cards."""
    import subprocess
    
    log.info(f"Extracting dumps for {len(card_ids)} cards...")
    
    # Run dump_pricing_text.py
    log.info("Dumping pricing pages...")
    cmd = ['python', 'src/pricing/dump_pricing_text.py', '--bank', bank.key]
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Pricing dump failed: {result.stderr}")
        return False
    
    # Run dump_rewards_text.py
    log.info("Dumping rewards PDFs...")
    cmd = ['python', 'src/rewards/dump_rewards_text.py', '--bank', bank.key]
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Rewards dump failed: {result.stderr}")
        return False
    
    return True


def extract_structured_data(card_ids: List[str], bank, force: bool = False):
    """Extract structured data (pricing + rewards) for specified cards."""
    import subprocess
    
    log.info(f"Extracting structured data for {len(card_ids)} cards...")
    
    # Run the deterministic pricing parser
    log.info("Extracting pricing data...")
    cmd = ['python', 'src/pricing/parse_pricing_deterministic.py', '--bank', bank.key]
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Pricing extraction failed: {result.stderr}")
        return False
    
    # Run extract_rewards_extended.py
    log.info("Extracting rewards data...")
    cmd = ['python', 'src/rewards/extract_rewards_extended.py', '--bank', bank.key]
    if force:
        cmd.append('--force')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error(f"Rewards extraction failed: {result.stderr}")
        return False
    
    return True


def merge_card_data(card_id: str, bank) -> Optional[Dict]:
    """Merge pricing and rewards data for a single card."""
    pricing_data = merge.find_record(
        merge.load_json_records(bank.extracted_pricing_path), card_id
    )
    rewards_data = merge.find_record(
        merge.load_json_records(bank.extracted_rewards_path), card_id
    )
    
    card = find_card_by_id(card_id, bank)
    if not card:
        return None
    
    return merge.merge_card(card, pricing_data, rewards_data)


def save_individual_card(card_id: str, data: Dict, cards_dir: Path):
    """Save individual card data to <cards_dir>/<card_id>.json"""
    cards_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = cards_dir / f"{card_id}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    log.info(f"✓ Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract comprehensive credit card data from supported banks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--url', help='Card URL to extract')
    input_group.add_argument('--card-id', help='Card ID from cleaned data')
    input_group.add_argument('--batch', type=int, metavar='N', help='Extract first N cards')
    input_group.add_argument('--list', action='store_true', help='List available cards')
    input_group.add_argument('--list-banks', action='store_true', help='List supported banks')
    
    # Options
    parser.add_argument('--bank', default='chase', help='Bank key (default: chase; see --list-banks)')
    parser.add_argument('--force', action='store_true', help='Force re-extraction even if data exists')
    parser.add_argument('--skip-dumps', action='store_true', help='Skip dump step (use existing dumps)')
    parser.add_argument('--output-dir', default=None, help='Output directory for individual card JSONs (default: data/<bank>/cards)')
    
    args = parser.parse_args()
    
    # Handle --list-banks
    if args.list_banks:
        list_banks()
        return
    
    bank = get_bank(args.bank)
    output_dir = Path(args.output_dir) if args.output_dir else bank.per_card_dir
    
    # Handle --list
    if args.list:
        list_available_cards(bank)
        return
    
    # Determine which cards to extract
    card_ids = []
    
    if args.card_id:
        card = find_card_by_id(args.card_id, bank)
        if not card:
            log.error(f"Card ID not found for bank '{bank.key}': {args.card_id}")
            log.info("Use --list to see available cards")
            sys.exit(1)
        card_ids = [args.card_id]
    
    elif args.batch:
        cards = load_cleaned_cards(bank)
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
    log.info(f"Bank: {bank.display_name} ({bank.key})")
    log.info(f"Cards to extract: {len(card_ids)}")
    log.info(f"Card IDs: {', '.join(card_ids)}")
    log.info(f"{'='*80}\n")
    
    # Step 1: Extract dumps (unless skipped)
    if not args.skip_dumps:
        log.info("STEP 1: Extracting raw dumps...")
        if not extract_dumps(card_ids, bank, args.force):
            log.error("Dump extraction failed")
            sys.exit(1)
    else:
        log.info("STEP 1: Skipped (using existing dumps)")
    
    # Step 2: Extract structured data
    log.info("\nSTEP 2: Extracting structured data...")
    if not extract_structured_data(card_ids, bank, args.force):
        log.error("Structured extraction failed")
        sys.exit(1)
    
    # Step 3: Merge and save individual card files
    log.info("\nSTEP 3: Merging and saving individual card files...")
    success_count = 0
    
    for card_id in card_ids:
        merged_data = merge_card_data(card_id, bank)
        if merged_data:
            save_individual_card(card_id, merged_data, output_dir)
            success_count += 1
        else:
            log.warning(f"✗ Failed to merge data for {card_id}")
    
    # Summary
    log.info(f"\n{'='*80}")
    log.info(f"EXTRACTION COMPLETE")
    log.info(f"{'='*80}")
    log.info(f"✓ Successfully extracted: {success_count}/{len(card_ids)} cards")
    log.info(f"✓ Individual card files: {output_dir}")
    log.info(f"✓ Combined pricing data: {bank.extracted_pricing_path}")
    log.info(f"✓ Combined rewards data: {bank.extracted_rewards_path}")
    log.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()
