"""
Extract partial rewards data from product page HTML for cards without RPA PDFs.

This is a fallback extractor for cards that don't have Rewards Program Agreement PDFs
linked from their product pages. It extracts earning categories from the marketing copy
already scraped in the earning_rates field.

Coverage: ~9 cards (Sapphire, Disney, Amazon, IHG Traveler, etc.)
Cost: ~$0.001/card × 9 = ~$0.01
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Optional
from dotenv import load_dotenv

import boto3
from botocore.exceptions import ClientError

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.schemas import RewardsHtmlFallback, ALLOWED_CATEGORIES, coerce_null_strings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def call_bedrock_with_retry(bedrock_runtime, model_id: str, tool_config: dict, messages: list, max_retries: int = 3) -> dict:
    """Call Bedrock with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.converse(
                modelId=model_id,
                messages=messages,
                toolConfig=tool_config
            )
            return response
        except ClientError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                log.warning(f"Bedrock call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")


def extract_rewards_from_html(card_id: str, card_name: str, html_text: str) -> Optional[RewardsHtmlFallback]:
    """Extract rewards data from product page HTML text using Bedrock."""
    
    # Initialize Bedrock client
    bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
    model_id = 'anthropic.claude-3-haiku-20240307-v1:0'
    
    # Build tool definition
    tool_config = {
        "tools": [{
            "toolSpec": {
                "name": "record_rewards_html_fallback",
                "description": "Record partial credit card rewards data extracted from product page marketing copy",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "earning_categories": {
                                "type": "array",
                                "description": "List of earning categories with rates. MUST include exactly one 'all_other' entry for base rate.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "category": {
                                            "type": "string",
                                            "description": f"Category name. MUST be one of: {', '.join(ALLOWED_CATEGORIES)}",
                                            "enum": ALLOWED_CATEGORIES
                                        },
                                        "rate": {"type": "number", "description": "Points/cash back per dollar"},
                                        "cap_usd": {"type": ["number", "null"], "description": "Annual spending cap in USD"},
                                        "cap_period": {"type": ["string", "null"], "description": "Cap period (annual, quarterly, etc.)"},
                                        "requires_activation": {"type": "boolean", "description": "Whether category requires activation"},
                                        "notes": {"type": ["string", "null"], "description": "Additional context"}
                                    },
                                    "required": ["category", "rate", "requires_activation"]
                                }
                            },
                            "cardmember_anniversary_benefit": {
                                "type": ["string", "null"],
                                "description": "Anniversary benefit description (e.g., free night certificate)"
                            }
                        },
                        "required": ["earning_categories"]
                    }
                }
            }
        }],
        "toolChoice": {"tool": {"name": "record_rewards_html_fallback"}}
    }
    
    # Build prompt
    prompt = f"""You are extracting credit card rewards data from PRODUCT PAGE MARKETING COPY, not a legal agreement.

IMPORTANT CONSTRAINTS:
1. This is marketing text, NOT a complete rewards agreement
2. Extract ONLY what is explicitly stated - do NOT infer redemption rules, transfer partners, or expiration policies
3. Skip vague marketing language like "premium rewards" - only extract specific rates like "5x points on travel"

CATEGORY VOCABULARY - YOU MUST USE EXACTLY ONE OF THESE (NO EXCEPTIONS):
{', '.join(ALLOWED_CATEGORIES)}

SPECIAL CASES:
- Disney purchases: Use "other" category with notes="Disney purchases at select locations"
- Marriott purchases: Use "other" category with notes="Marriott Bonvoy purchases"
- IHG purchases: Use "other" category with notes="IHG purchases"
- Brand-specific spending: ALWAYS use "other" with descriptive notes

MANDATORY RULES:
- MUST include exactly one "all_other" entry for the base earning rate
- If base rate not stated, infer 1x and add note: "inferred from absence of explicit base rate"
- If category is "other", notes field is REQUIRED (explain what "other" means)
- Use "travel_chase_portal" for Chase Travel/Ultimate Rewards portal bookings
- Use "travel" for general travel (airlines, hotels booked direct)
- NEVER invent new category names - if unsure, use "other" with notes

CARD: {card_name}

PRODUCT PAGE TEXT:
{html_text}

Extract earning_categories and anniversary_benefit (if mentioned).
"""
    
    messages = [{
        "role": "user",
        "content": [{"text": prompt}]
    }]
    
    try:
        response = call_bedrock_with_retry(bedrock_runtime, model_id, tool_config, messages)
        
        # Extract tool use
        if response.get('stopReason') == 'tool_use':
            for content_block in response['output']['message']['content']:
                if 'toolUse' in content_block:
                    tool_input = content_block['toolUse']['input']
                    
                    # Coerce null strings
                    tool_input = coerce_null_strings(tool_input)
                    
                    # Build RewardsHtmlFallback object
                    rewards_data = {
                        'card_id': card_id,
                        'card_name': card_name,
                        'source_type': 'product_page_html',
                        'source_text_length': len(html_text),
                        'earning_categories': tool_input.get('earning_categories', []),
                        'cardmember_anniversary_benefit': tool_input.get('cardmember_anniversary_benefit')
                    }
                    
                    # Validate with Pydantic
                    rewards = RewardsHtmlFallback(**rewards_data)
                    return rewards
        
        log.error(f"Unexpected Bedrock response format: {response.get('stopReason')}")
        return None
        
    except Exception as e:
        log.error(f"Failed to extract rewards from HTML for {card_name}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Extract rewards from product page HTML (fallback)')
    parser.add_argument('--force', action='store_true', help='Force re-extraction')
    parser.add_argument('--limit', type=int, help='Limit number of cards to process (for debugging)')
    args = parser.parse_args()
    
    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, 'output')
    output_path = os.path.join(output_dir, 'extracted_rewards_html_fallback.json')
    
    # Load cleaned cards
    clean_cards_path = os.path.join(output_dir, 'chase_cards_clean.json')
    with open(clean_cards_path, 'r', encoding='utf-8') as f:
        clean_cards = json.load(f)
    
    # Load raw cards (for earning_rates text)
    raw_cards_path = os.path.join(output_dir, 'chase_cards.json')
    with open(raw_cards_path, 'r', encoding='utf-8') as f:
        raw_cards = json.load(f)
    
    # Create lookup for earning_rates
    earning_rates_lookup = {}
    for raw_card in raw_cards:
        card_name = raw_card.get('card_name', '').strip()
        earning_rates = raw_card.get('earning_rates', '')
        if earning_rates and len(earning_rates) >= 200:  # Non-trivial text
            earning_rates_lookup[card_name] = earning_rates
    
    # Load existing results if present
    existing_results = []
    processed_card_ids = set()
    
    if os.path.exists(output_path) and not args.force:
        with open(output_path, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)
            processed_card_ids = {r['card_id'] for r in existing_results}
        log.info(f"Resuming: {len(processed_card_ids)} cards already processed")
    
    results = existing_results.copy()
    
    # Filter cards: null rewards_agreement_url AND has earning_rates text
    cards_to_process = []
    for card in clean_cards:
        card_id = card.get('card_id')
        card_name = card.get('card_name')
        rewards_url = card.get('rewards_agreement_url')
        
        # Skip if already processed
        if card_id in processed_card_ids:
            continue
        
        # Skip if has valid RPA PDF URL
        if rewards_url and rewards_url.startswith('http') and '.pdf' in rewards_url.lower():
            continue
        
        # Skip if no earning_rates text
        if card_name not in earning_rates_lookup:
            log.info(f"Skipping {card_name} - no earning_rates text")
            continue
        
        # Skip Slate (balance transfer card, no rewards)
        if 'Slate' in card_name:
            log.info(f"Skipping {card_name} - balance transfer card")
            continue
        
        cards_to_process.append(card)
    
    log.info(f"Found {len(cards_to_process)} cards for HTML fallback extraction")
    
    # Apply limit if specified
    if args.limit:
        cards_to_process = cards_to_process[:args.limit]
        log.info(f"Limited to {len(cards_to_process)} cards")
    
    success_count = 0
    fail_count = 0
    
    for card in cards_to_process:
        card_id = card.get('card_id')
        card_name = card.get('card_name')
        earning_rates = earning_rates_lookup.get(card_name, '')
        
        log.info(f"\nProcessing: {card_name}")
        log.info(f"  Source text length: {len(earning_rates)} chars")
        
        try:
            rewards = extract_rewards_from_html(card_id, card_name, earning_rates)
            
            if rewards:
                results.append(rewards.model_dump())
                success_count += 1
                log.info(f"  [OK] Extracted {len(rewards.earning_categories)} earning categories")
                
                # Write incrementally
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
            else:
                fail_count += 1
                log.error(f"  [FAIL] Extraction failed")
                
        except Exception as e:
            fail_count += 1
            log.error(f"  [ERROR] {e}")
    
    # Summary
    log.info("\n" + "="*80)
    log.info("SUMMARY")
    log.info("="*80)
    log.info(f"Extracted: {success_count}")
    log.info(f"Failed: {fail_count}")
    log.info(f"Output: {output_path}")
    log.info("="*80)


if __name__ == '__main__':
    main()
