"""Dump raw rewards agreement text (PDF → Text) for reuse."""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from src.common.pdf_utils import download_and_extract_pdf_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


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


def write_dump_file(dump_path: str, card_id: str, card_name: str, url: str, content: str):
    """Write dump file with YAML frontmatter."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    frontmatter = f"""---
card_id: {card_id}
card_name: {card_name}
rewards_agreement_url: {url}
dumped_at: {timestamp}
---

"""
    
    with open(dump_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter)
        f.write(content)
    
    log.info(f"  ✓ Wrote {len(content)} chars to {os.path.basename(dump_path)}")


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Dump rewards agreement text")
    parser.add_argument('--force', action='store_true', help='Force re-dump even if files exist')
    parser.add_argument('--limit', type=int, help='Limit number of cards to process (for debugging)')
    args = parser.parse_args()
    
    # Setup absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    output_dir = os.path.join(project_root, 'data')
    dump_dir = os.path.join(output_dir, 'raw', 'rewards')
    
    # Ensure dump directory exists
    os.makedirs(dump_dir, exist_ok=True)
    
    # Load cleaned cards
    input_path = os.path.join(output_dir, 'chase_cards_clean.json')
    log.info(f"Loading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        cards = json.load(f)
    
    # Filter for cards with PDF rewards agreement URLs
    cards_with_pdf = [
        c for c in cards 
        if c.get('rewards_agreement_url') and 
        '.pdf' in c.get('rewards_agreement_url').lower()
    ]
    log.info(f"Found {len(cards_with_pdf)} cards with PDF rewards agreements")
    
    # Apply limit if specified
    if args.limit:
        cards_with_pdf = cards_with_pdf[:args.limit]
        log.info(f"Limited to {len(cards_with_pdf)} cards")
    
    log.info(f"Processing {len(cards_with_pdf)} cards")
    
    success_count = 0
    skip_count = 0
    
    for idx, card in enumerate(cards_with_pdf, 1):
        card_id = card['card_id']
        card_name = card['card_name']
        rewards_url = card['rewards_agreement_url']
        
        log.info(f"\n[{idx}/{len(cards_with_pdf)}] {card_name}")
        
        # Check if should skip
        dump_path = os.path.join(dump_dir, f"{card_id}.txt")
        if should_skip_dump(dump_path, args.force):
            skip_count += 1
            continue
        
        try:
            # Download and extract PDF text
            log.info(f"  Downloading PDF: {rewards_url}")
            pdf_text = download_and_extract_pdf_text(rewards_url)
            
            if not pdf_text:
                raise Exception("PDF extraction returned empty text")
            
            log.info(f"  ✓ Extracted {len(pdf_text)} chars from PDF")
            
            # Write dump file
            write_dump_file(dump_path, card_id, card_name, rewards_url, pdf_text)
            success_count += 1
            
        except Exception as e:
            log.error(f"  ✗ Failed: {e}")
            continue
    
    # Summary
    log.info(f"\n{'='*80}")
    log.info(f"SUMMARY")
    log.info(f"{'='*80}")
    log.info(f"✓ Dumped: {success_count}")
    log.info(f"⊘ Skipped: {skip_count}")
    log.info(f"✗ Failed: {len(cards_with_pdf) - success_count - skip_count}")
    log.info(f"Output: {dump_dir}")


if __name__ == '__main__':
    main()
