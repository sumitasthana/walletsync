"""Extract extended pricing data from Schumer Box dumps using AWS Bedrock.

DEPRECATED as of 2026-04-21. Replaced by src/parse_pricing_deterministic.py.
Kept for reference only — do not call in the pipeline.

This LLM-based approach has been superseded by deterministic HTML table parsing which:
- Has 100% success rate (vs 98% LLM)
- Has 0 hallucinations (vs 3 LLM hallucinations)
- Costs $0 (vs ~$0.07 per run)
- Runs in <1 second (vs ~5 minutes)
- Is fully reproducible and unit-testable

See PATH_B_COMPLETE.md for migration details.
"""

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
from schemas import PricingExtended, coerce_null_strings

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


def extract_pricing_with_bedrock(markdown_text: str, card_id: str, card_name: str, pricing_url: str) -> Optional[dict]:
    """
    Extract extended pricing data from Schumer Box markdown using Bedrock.
    
    Args:
        markdown_text: Schumer Box content in markdown
        card_id: Card identifier
        card_name: Card name
        pricing_url: Pricing terms URL
        
    Returns:
        Dictionary with extracted pricing data, or None if failed
    """
    log.info(f"Extracting pricing for {card_name}...")
    
    try:
        # Initialize Bedrock Runtime client
        region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        bedrock = boto3.client('bedrock-runtime', region_name=region)
        
        # Define the tool for structured extraction
        tool_config = {
            "tools": [
                {
                    "toolSpec": {
                        "name": "record_pricing_extended",
                        "description": "Record comprehensive pricing data from a credit card Schumer Box disclosure",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "purchase_apr_min": {
                                        "type": "number",
                                        "description": "Minimum purchase APR percentage (e.g., 18.24 for 18.24%). Return null if not disclosed."
                                    },
                                    "purchase_apr_max": {
                                        "type": "number",
                                        "description": "Maximum purchase APR percentage (e.g., 27.74 for 27.74%). Return null if not disclosed."
                                    },
                                    "purchase_apr_intro_pct": {
                                        "type": "number",
                                        "description": "Intro purchase APR percentage. Return null if no intro period."
                                    },
                                    "purchase_apr_intro_months": {
                                        "type": "integer",
                                        "description": "Intro purchase APR duration in months. Return null if no intro period."
                                    },
                                    "bt_apr_min": {
                                        "type": "number",
                                        "description": "Minimum balance transfer APR percentage. Return null if not disclosed."
                                    },
                                    "bt_apr_max": {
                                        "type": "number",
                                        "description": "Maximum balance transfer APR percentage. Return null if not disclosed."
                                    },
                                    "bt_apr_intro_pct": {
                                        "type": "number",
                                        "description": "Intro balance transfer APR percentage. Return null if no intro period."
                                    },
                                    "bt_apr_intro_months": {
                                        "type": "integer",
                                        "description": "Intro balance transfer APR duration in months. Return null if no intro period."
                                    },
                                    "bt_intro_window_days": {
                                        "type": "integer",
                                        "description": "Days to complete balance transfer to get intro rate (e.g., 60 for 'within 60 days'). Return null if not specified."
                                    },
                                    "cash_advance_apr": {
                                        "type": "number",
                                        "description": "Cash advance APR percentage. This is required."
                                    },
                                    "penalty_apr_max": {
                                        "type": "number",
                                        "description": "Maximum penalty APR percentage. Return null if not disclosed."
                                    },
                                    "foreign_transaction_fee_pct": {
                                        "type": "number",
                                        "description": "Foreign transaction fee as percentage (e.g., 3.0 for 3%). This is required."
                                    },
                                    "balance_transfer_fee_pct": {
                                        "type": "number",
                                        "description": "Balance transfer fee percentage (e.g., 5.0 for 5%). Return null if not charged."
                                    },
                                    "balance_transfer_fee_min_usd": {
                                        "type": "integer",
                                        "description": "Minimum balance transfer fee in USD. Return null if not specified."
                                    },
                                    "balance_transfer_fee_max_usd": {
                                        "type": "integer",
                                        "description": "Maximum balance transfer fee in USD. Return null if not specified."
                                    },
                                    "cash_advance_fee_pct": {
                                        "type": "number",
                                        "description": "Cash advance fee percentage. Return null if not charged."
                                    },
                                    "cash_advance_fee_min_usd": {
                                        "type": "integer",
                                        "description": "Minimum cash advance fee in USD. Return null if not specified."
                                    },
                                    "late_payment_fee_max_usd": {
                                        "type": "integer",
                                        "description": "Maximum late payment fee in USD. This is required."
                                    },
                                    "authorized_user_fee_usd": {
                                        "type": "integer",
                                        "description": "Authorized user fee in USD. Return null if no fee is charged. Most cards do NOT charge this fee."
                                    },
                                    "apr_index": {
                                        "type": "string",
                                        "description": "APR index name (e.g., 'Prime Rate'). Return null if not disclosed."
                                    },
                                    "purchase_apr_margin": {
                                        "type": "number",
                                        "description": "Purchase APR margin over index in percentage points (e.g., 13.99 for 'Prime + 13.99%'). Return null if not disclosed."
                                    },
                                    "apr_disclosure_date": {
                                        "type": "string",
                                        "description": "Date pricing info was accurate in YYYY-MM-DD format. ONLY populate if document explicitly states 'Information accurate as of MM/DD/YYYY' or similar. Return null otherwise."
                                    }
                                },
                                "required": [
                                    "cash_advance_apr",
                                    "foreign_transaction_fee_pct",
                                    "late_payment_fee_max_usd"
                                ]
                            }
                        }
                    }
                }
            ]
        }
        
        # Construct the prompt
        user_message = f"""You are analyzing a credit card Schumer Box pricing disclosure table. Extract ALL pricing fields accurately.

CRITICAL INSTRUCTIONS:

1. **Distinguish FEES from APRs**: 
   - Look in the "Fees" section for fees (foreign transaction, balance transfer fee, cash advance fee, late payment)
   - Look in the "Interest Rates and Interest Charges" section for APRs
   - DO NOT confuse APR percentages with fee percentages

2. **Return null for absent fields**:
   - If a field is not disclosed, return null
   - Most cards have NO authorized_user_fee_usd — that's null, not 0
   - If there's no intro APR, both intro_pct and intro_months should be null

3. **APR Ranges**:
   - For "18.24% to 27.74%" or "18.24%–27.74%": purchase_apr_min=18.24, purchase_apr_max=27.74
   - Extract ONLY the numeric values, no % symbols

4. **Intro APR**:
   - For "0% intro APR for 15 months from account opening on purchases and balance transfers":
     * purchase_apr_intro_pct=0.0, purchase_apr_intro_months=15
     * bt_apr_intro_pct=0.0, bt_apr_intro_months=15
   - For "0% intro APR for 15 months on purchases": only set purchase intro fields
   - Look for language like "first 15 months", "for 15 months", "intro period of 15 months"

5. **Balance Transfer Window**:
   - For "must transfer within 60 days": bt_intro_window_days=60
   - Look for "within X days of account opening"

6. **Prime Rate Disclosures**:
   - If APR is "based on Prime Rate" or "varies with Prime Rate": apr_index="Prime Rate"
   - For "Prime + 13.99%": purchase_apr_margin=13.99
   - Extract margin from language like "Prime Rate + X.XX%"

7. **Fee Structures**:
   - For "5% of amount, $5 minimum": balance_transfer_fee_pct=5.0, balance_transfer_fee_min_usd=5
   - For "$5 or 5%, whichever is greater": same as above
   - For "up to $40": late_payment_fee_max_usd=40

8. **Disclosure Date**:
   - ONLY populate if document explicitly states "Information accurate as of MM/DD/YYYY"
   - Convert to YYYY-MM-DD format
   - Return null if not stated

Here is the Schumer Box pricing table in Markdown format:

{markdown_text}

Extract all pricing fields and call the record_pricing_extended tool."""
        
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
                    if tool_use.get('name') == 'record_pricing_extended':
                        raw_data = tool_use.get('input', {})
                        
                        # Coerce null strings to None
                        coerced_data = coerce_null_strings(raw_data)
                        
                        # Add identifiers
                        coerced_data['card_id'] = card_id
                        coerced_data['card_name'] = card_name
                        coerced_data['pricing_terms_url'] = pricing_url
                        
                        # Validate with Pydantic
                        pricing_obj = PricingExtended.model_validate(coerced_data)
                        pricing_data = pricing_obj.model_dump()
                        
                        log.info(f"✓ Successfully extracted pricing for {card_name}")
                        return pricing_data
            
            log.warning(f"Tool use response but no record_pricing_extended found for {card_name}")
            return None
        else:
            log.warning(f"Unexpected stop reason: {stop_reason} for {card_name}")
            return None
            
    except Exception as e:
        log.error(f"Bedrock extraction failed for {card_name}: {e}")
        return None


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Extract extended pricing data")
    parser.add_argument('--force', action='store_true', help='Force re-extraction even if already processed')
    parser.add_argument('--limit', type=int, help='Limit number of cards to process (for debugging)')
    args = parser.parse_args()
    
    # Setup absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, 'output')
    dump_dir = os.path.join(output_dir, 'raw', 'pricing')
    output_path = os.path.join(output_dir, 'extracted_pricing_extended.json')
    
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
    
    # Find all pricing dump files
    dump_files = [f for f in os.listdir(dump_dir) if f.endswith('.md')]
    log.info(f"Found {len(dump_files)} pricing dump files")
    
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
        pricing_url = frontmatter.get('pricing_terms_url', '')
        
        log.info(f"\nProcessing: {card_name}")
        
        # Skip if already processed
        if card_id in processed_card_ids:
            log.info(f"  Skipping (already processed)")
            skip_count += 1
            continue
        
        # Extract pricing data
        pricing_data = extract_pricing_with_bedrock(body, card_id, card_name, pricing_url)
        
        if pricing_data:
            results.append(pricing_data)
            success_count += 1
            
            # Save incrementally
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        else:
            log.warning(f"  ✗ Failed to extract pricing")
        
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
