"""Extract extended rewards data from PDF dumps using AWS Bedrock."""

import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from dump_utils import parse_frontmatter
from schemas import (
    RewardsExtended, 
    EarningCategory, 
    RedemptionOption, 
    TransferPartner,
    ALLOWED_CATEGORIES,
    coerce_null_strings,
    validate_rewards_categories
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def bedrock_converse_with_retry(bedrock, **kwargs):
    """Call bedrock.converse with retry on throttling."""
    for attempt in range(3):
        try:
            return bedrock.converse(**kwargs)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['ThrottlingException', 'ServiceUnavailableException']:
                if attempt < 2:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    log.warning(f"Throttled, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
            else:
                raise


def coerce_nested_nulls(data: dict) -> dict:
    """Recursively coerce null strings in nested structures."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and value.lower() in ['null', 'none', '']:
                result[key] = None
            elif isinstance(value, dict):
                result[key] = coerce_nested_nulls(value)
            elif isinstance(value, list):
                result[key] = [coerce_nested_nulls(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result
    return data


def extract_rewards_with_bedrock(pdf_text: str, card_id: str, card_name: str, rewards_url: str) -> Optional[dict]:
    """
    Extract extended rewards data from PDF text using Bedrock.
    
    Args:
        pdf_text: Rewards agreement text
        card_id: Card identifier
        card_name: Card name
        rewards_url: Rewards agreement URL
        
    Returns:
        Dictionary with extracted rewards data, or None if failed
    """
    log.info(f"Extracting rewards for {card_name}...")
    
    try:
        # Initialize Bedrock Runtime client
        region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        bedrock = boto3.client('bedrock-runtime', region_name=region)
        
        # Define the tool for structured extraction
        tool_config = {
            "tools": [
                {
                    "toolSpec": {
                        "name": "record_rewards_extended",
                        "description": "Record comprehensive rewards program data from a credit card rewards agreement",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "reward_currency": {
                                        "type": "string",
                                        "description": "Reward currency type: 'Cash Back', 'Points', or 'Miles'"
                                    },
                                    "point_value_cents_baseline": {
                                        "type": "number",
                                        "description": "CASH redemption value in cents per point (e.g., 1.0 for UR points cash back, 0.5 for Marriott cash). Return null if no cash redemption option exists."
                                    },
                                    "earning_categories": {
                                        "type": "array",
                                        "description": "List of earning categories. MUST include one entry with category='all_other' for the base rate.",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "category": {
                                                    "type": "string",
                                                    "description": "Category from ALLOWED_CATEGORIES list"
                                                },
                                                "rate": {
                                                    "type": "number",
                                                    "description": "Earn rate (e.g., 3.0 for 3x or 3%)"
                                                },
                                                "cap_usd": {
                                                    "type": "integer",
                                                    "description": "Spending cap in USD. Null if no cap."
                                                },
                                                "cap_period": {
                                                    "type": "string",
                                                    "description": "Cap period: 'quarterly', 'annual', 'per_transaction'. Null if no cap."
                                                },
                                                "requires_activation": {
                                                    "type": "boolean",
                                                    "description": "True if category requires activation"
                                                },
                                                "notes": {
                                                    "type": "string",
                                                    "description": "Additional context. REQUIRED if category='other'."
                                                }
                                            },
                                            "required": ["category", "rate"]
                                        }
                                    },
                                    "redemption_minimum_usd": {
                                        "type": "integer",
                                        "description": "Minimum redemption amount in USD. Null if no minimum."
                                    },
                                    "redemption_options": {
                                        "type": "array",
                                        "description": "Available redemption methods",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "method": {
                                                    "type": "string",
                                                    "description": "Method: 'cash_back', 'statement_credit', 'travel_portal', 'transfer', 'pay_with_points', 'gift_cards', 'amazon', 'apple'"
                                                },
                                                "value_cents_per_point": {
                                                    "type": "number",
                                                    "description": "Redemption value in cents per point (e.g., 1.0 for 1cpp, 1.25 for travel portal)"
                                                },
                                                "notes": {
                                                    "type": "string",
                                                    "description": "Additional details"
                                                }
                                            },
                                            "required": ["method", "value_cents_per_point"]
                                        }
                                    },
                                    "transfer_partners": {
                                        "type": "array",
                                        "description": "Loyalty program transfer partners",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "partner_name": {
                                                    "type": "string",
                                                    "description": "Partner program name (e.g., 'United MileagePlus', 'Marriott Bonvoy')"
                                                },
                                                "ratio_from": {
                                                    "type": "integer",
                                                    "description": "Points you give up (e.g., 3 for 3:1 transfer where 3 points = 1 mile)"
                                                },
                                                "ratio_to": {
                                                    "type": "integer",
                                                    "description": "Points you receive (e.g., 1 for 3:1 transfer where 3 points = 1 mile)"
                                                },
                                                "notes": {
                                                    "type": "string",
                                                    "description": "Transfer details"
                                                }
                                            },
                                            "required": ["partner_name", "ratio_from", "ratio_to"]
                                        }
                                    },
                                    "points_expiration_months": {
                                        "type": "integer",
                                        "description": "Months until points expire. Null if points don't expire."
                                    },
                                    "bonus_disqualifying_products": {
                                        "type": "array",
                                        "description": "Product names that disqualify signup bonus (exact names as written)",
                                        "items": {"type": "string"}
                                    },
                                    "cardmember_anniversary_benefit": {
                                        "type": "string",
                                        "description": "Annual benefit description, single sentence. Null if none."
                                    }
                                },
                                "required": ["reward_currency", "earning_categories"]
                            }
                        }
                    }
                }
            ]
        }
        
        # Construct the prompt
        allowed_cats_str = ", ".join(ALLOWED_CATEGORIES)
        
        user_message = f"""You are analyzing a credit card rewards program agreement. Extract ALL rewards fields accurately.

CRITICAL INSTRUCTIONS:

1. **ALLOWED_CATEGORIES for earning_categories**:
   Choose the closest match from this list: {allowed_cats_str}
   
   Use 'other' ONLY if nothing fits, and you MUST populate 'notes' with the original phrasing in that case.

2. **MANDATORY all_other entry**:
   Every card has a base rate. You MUST include an entry with category='all_other' in earning_categories.
   
   - If the document explicitly states a base rate (e.g., "1% on all other purchases"), use that rate.
   - If the document does NOT explicitly state a base rate, infer 1.0 (1x or 1%) and add a note: "inferred from absence of explicit base rate"

3. **Capture caps and activation**:
   - For "5% on up to $1,500 each quarter": cap_usd=1500, cap_period="quarterly"
   - For "in bonus categories you activate": requires_activation=true
   - For "5% on rotating categories": category="rotating_5pct"

4. **Transfer ratios direction**:
   - ratio_from is what you GIVE UP
   - ratio_to is what you RECEIVE
   - 1:1 transfer = ratio_from=1, ratio_to=1
   - Marriott Bonvoy → airline at 3:1 (3 Bonvoy = 1 airline mile) = ratio_from=3, ratio_to=1

5. **point_value_cents_baseline**:
   This is the CASH redemption rate ONLY.
   - Ultimate Rewards points = 1.0¢ for cash back
   - Marriott Bonvoy = ~0.5¢ for cash (if available)
   - If there's NO cash redemption option, return null

6. **bonus_disqualifying_products**:
   Extract product names EXACTLY as written (e.g., "Sapphire Preferred", not "CSP").
   Return empty list if none mentioned.

7. **cardmember_anniversary_benefit**:
   Single sentence summarizing the recurring annual perk.
   Return null if no anniversary benefit.

8. **redemption_options**:
   List all redemption methods with their values:
   - cash_back: typically 1.0cpp
   - statement_credit: typically 1.0cpp
   - travel_portal: often 1.25cpp or 1.5cpp for premium cards
   - transfer: 1.0cpp (transfer value varies by partner)

Here is the rewards agreement document:

{pdf_text[:15000]}

Extract all rewards fields and call the record_rewards_extended tool."""
        
        # Call Bedrock Converse API with retry
        response = bedrock_converse_with_retry(
            bedrock,
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user_message}]
                }
            ],
            toolConfig=tool_config
        )
        
        # Parse the response
        stop_reason = response.get('stopReason')
        
        if stop_reason == 'tool_use':
            # Extract tool use from response
            output_message = response.get('output', {}).get('message', {})
            content = output_message.get('content', [])
            
            for item in content:
                if 'toolUse' in item:
                    tool_use = item['toolUse']
                    if tool_use.get('name') == 'record_rewards_extended':
                        raw_data = tool_use.get('input', {})
                        
                        # Coerce null strings recursively
                        coerced_data = coerce_nested_nulls(raw_data)
                        
                        # Add identifiers
                        coerced_data['card_id'] = card_id
                        coerced_data['card_name'] = card_name
                        coerced_data['rewards_agreement_url'] = rewards_url
                        
                        # Validate with Pydantic
                        rewards_obj = RewardsExtended.model_validate(coerced_data)
                        
                        # Additional validation
                        validate_rewards_categories(rewards_obj)
                        
                        rewards_data = rewards_obj.model_dump()
                        
                        log.info(f"✓ Successfully extracted rewards for {card_name}")
                        return rewards_data
            
            log.warning(f"Tool use response but no record_rewards_extended found for {card_name}")
            return None
        else:
            log.warning(f"Unexpected stop reason: {stop_reason} for {card_name}")
            return None
            
    except Exception as e:
        log.error(f"Bedrock extraction failed for {card_name}: {e}")
        return None


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Extract extended rewards data")
    parser.add_argument('--force', action='store_true', help='Force re-extraction even if already processed')
    parser.add_argument('--limit', type=int, help='Limit number of cards to process (for debugging)')
    args = parser.parse_args()
    
    # Setup absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, 'output')
    dump_dir = os.path.join(output_dir, 'raw', 'rewards')
    output_path = os.path.join(output_dir, 'extracted_rewards_extended.json')
    
    # Load existing results if present (for resume)
    existing_results = []
    processed_card_ids = set()
    
    if os.path.exists(output_path) and not args.force:
        with open(output_path, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
            # Skip metadata record
            existing_results = [r for r in all_results if '_meta' not in r]
            processed_card_ids = {r['card_id'] for r in existing_results}
        log.info(f"Resuming: {len(processed_card_ids)} cards already processed")
    
    results = existing_results.copy()
    
    # Find all rewards dump files
    dump_files = [f for f in os.listdir(dump_dir) if f.endswith('.txt')]
    log.info(f"Found {len(dump_files)} rewards dump files")
    
    # Apply limit if specified
    if args.limit:
        dump_files = dump_files[:args.limit]
        log.info(f"Limited to {len(dump_files)} files")
    
    success_count = 0
    skip_count = 0
    
    for dump_file in dump_files:
        dump_path = os.path.join(dump_dir, dump_file)
        
        # Parse frontmatter
        frontmatter, body = parse_frontmatter(dump_path)
        card_id = frontmatter.get('card_id', '')
        card_name = frontmatter.get('card_name', '')
        rewards_url = frontmatter.get('rewards_agreement_url', '')
        
        log.info(f"\nProcessing: {card_name}")
        
        # Skip if already processed
        if card_id in processed_card_ids:
            log.info(f"  Skipping (already processed)")
            skip_count += 1
            continue
        
        # Extract rewards data
        rewards_data = extract_rewards_with_bedrock(body, card_id, card_name, rewards_url)
        
        if rewards_data:
            results.append(rewards_data)
            success_count += 1
            
            # Save incrementally
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        else:
            log.warning(f"  ✗ Failed to extract rewards")
        
        # Small delay between requests
        time.sleep(1)
    
    # Summary
    log.info(f"\n{'='*80}")
    log.info(f"SUMMARY")
    log.info(f"{'='*80}")
    log.info(f"✓ Extracted: {success_count}")
    log.info(f"⊘ Skipped: {skip_count}")
    log.info(f"✗ Failed: {len(dump_files) - success_count - skip_count}")
    log.info(f"Output: {output_path}")
    
    # Print sample
    if results:
        log.info(f"\n{'='*80}")
        log.info(f"SAMPLE RECORD")
        log.info(f"{'='*80}")
        print(json.dumps(results[0], indent=2))


if __name__ == '__main__':
    main()
