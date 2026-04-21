"""Extract fee data from Chase pricing terms using AWS Bedrock and Playwright."""

import json
import logging
import os
import sys
import time
from typing import Optional

import boto3
from dotenv import load_dotenv
from markdownify import markdownify as md
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def scrape_pricing_page_to_markdown(url: str) -> Optional[str]:
    """
    Scrape the pricing terms page and convert to Markdown.
    
    Args:
        url: The pricing_terms_url to scrape
        
    Returns:
        Markdown text of the Schumer Box table, or None if failed
    """
    log.info(f"Scraping pricing page: {url}")
    
    try:
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
            
            # Navigate to pricing page
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for content to load
            time.sleep(3)
            
            # Try to find the main content area with Schumer Box
            # Common selectors for pricing tables
            content_html = None
            
            # Try multiple selectors
            selectors = [
                "table",  # Generic table
                "[class*='schumer']",  # Schumer box specific
                "[class*='pricing']",  # Pricing table
                "main",  # Main content
                "body",  # Fallback to entire body
            ]
            
            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        content_html = element.inner_html()
                        log.info(f"Found content using selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not content_html:
                # Fallback: get entire page content
                content_html = page.content()
                log.warning("Using full page content as fallback")
            
            browser.close()
            
            # Convert HTML to Markdown
            markdown_text = md(content_html, heading_style="ATX")
            
            return markdown_text
            
    except Exception as e:
        log.error(f"Failed to scrape {url}: {e}")
        return None


def extract_fees_with_bedrock(markdown_text: str, card_name: str) -> Optional[dict]:
    """
    Extract fee data from markdown text using AWS Bedrock Claude 3 Haiku.
    
    Args:
        markdown_text: The markdown content from pricing page
        card_name: Name of the card for logging
        
    Returns:
        Dictionary with extracted fee data, or None if failed
    """
    log.info(f"Extracting fees for {card_name} using Bedrock...")
    
    try:
        # Initialize Bedrock Runtime client
        # Region can be set via AWS_DEFAULT_REGION in .env or will use default
        region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        bedrock = boto3.client('bedrock-runtime', region_name=region)
        
        # Define the tool for structured extraction
        tool_config = {
            "tools": [
                {
                    "toolSpec": {
                        "name": "record_fee_data",
                        "description": "Record the fee data extracted from a credit card pricing terms document",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "foreign_transaction_fee_percentage": {
                                        "type": "number",
                                        "description": "The foreign transaction fee as a percentage (e.g., 3.0 for 3%)"
                                    },
                                    "balance_transfer_fee_description": {
                                        "type": "string",
                                        "description": "Full description of the balance transfer fee (e.g., 'Either $5 or 5% of the amount, whichever is greater')"
                                    },
                                    "late_penalty_fee_usd": {
                                        "type": "integer",
                                        "description": "The late payment penalty fee in USD (e.g., 40)"
                                    },
                                    "cash_advance_apr": {
                                        "type": "number",
                                        "description": "The APR for cash advances as a percentage (e.g., 29.99)"
                                    }
                                },
                                "required": [
                                    "foreign_transaction_fee_percentage",
                                    "balance_transfer_fee_description",
                                    "late_penalty_fee_usd",
                                    "cash_advance_apr"
                                ]
                            }
                        }
                    }
                }
            ]
        }
        
        # Construct the prompt
        user_message = f"""You are analyzing a credit card pricing terms document (Schumer Box). 
Extract the following fee information and invoke the record_fee_data tool with the EXACT types specified:

1. **foreign_transaction_fee_percentage** (NUMBER): Extract ONLY the percentage number from the "Foreign Transaction" fee row. 
   - Example: "3% of each transaction" → 3.0
   - If "None" or "$0" → 0
   
2. **balance_transfer_fee_description** (STRING): Extract the full text describing the balance transfer fee from the "Balance Transfer" fee row.
   - Example: "Either $5 or 5% of the amount of each transfer, whichever is greater"
   - NOT the APR - look for the FEE section, not the APR section
   
3. **late_penalty_fee_usd** (INTEGER): Extract ONLY the dollar amount from the "Late Payment" fee row.
   - Example: "Up to $40" → 40
   - If range like "$30 to $40" → 40 (use the maximum)
   
4. **cash_advance_apr** (NUMBER): Extract ONLY the percentage number from the "Cash Advance APR" row.
   - Example: "28.49%" → 28.49
   - If variable, use the stated rate

IMPORTANT: 
- Use ONLY numbers for foreign_transaction_fee_percentage, late_penalty_fee_usd, and cash_advance_apr
- Do NOT include "%" symbols or "$" in numeric fields
- Look in the FEES section of the table, not the APR/Interest Rates section for fees

Here is the pricing document in Markdown format:

{markdown_text}

Extract these four values and call the record_fee_data tool."""
        
        # Call Bedrock Converse API
        response = bedrock.converse(
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
                    if tool_use.get('name') == 'record_fee_data':
                        fee_data = tool_use.get('input', {})
                        log.info(f"Successfully extracted fees for {card_name}")
                        return fee_data
            
            log.warning(f"Tool use response but no record_fee_data found for {card_name}")
            return None
        else:
            log.warning(f"Unexpected stop reason: {stop_reason} for {card_name}")
            # Try to get text response for debugging
            output_message = response.get('output', {}).get('message', {})
            content = output_message.get('content', [])
            for item in content:
                if 'text' in item:
                    log.info(f"Model response: {item['text'][:200]}")
            return None
            
    except Exception as e:
        log.error(f"Bedrock extraction failed for {card_name}: {e}")
        return None


def main():
    """Main execution function."""
    
    # Load the cleaned card data
    log.info("Loading chase_cards_clean.json...")
    with open('output/chase_cards_clean.json', 'r', encoding='utf-8') as f:
        cards = json.load(f)
    
    # Filter for cards with pricing_terms_url
    cards_with_pricing = [c for c in cards if c.get('pricing_terms_url')]
    log.info(f"Found {len(cards_with_pricing)} cards with pricing_terms_url")
    
    # Take first 3 as test batch
    test_cards = cards_with_pricing[:3]
    log.info(f"Processing {len(test_cards)} test cards")
    
    results = []
    
    for idx, card in enumerate(test_cards, 1):
        card_name = card.get('card_name', 'Unknown')
        pricing_url = card.get('pricing_terms_url')
        
        log.info(f"\n{'='*80}")
        log.info(f"Processing card {idx}/{len(test_cards)}: {card_name}")
        log.info(f"{'='*80}")
        
        # Step 1: Scrape and convert to Markdown
        markdown_text = scrape_pricing_page_to_markdown(pricing_url)
        
        if not markdown_text:
            log.error(f"Failed to scrape pricing page for {card_name}")
            continue
        
        # Print raw markdown for first card
        if idx == 1:
            log.info("\n" + "="*80)
            log.info("RAW MARKDOWN OUTPUT (First Card)")
            log.info("="*80)
            # Print first 2000 characters to verify table conversion
            print(markdown_text[:2000])
            log.info("="*80 + "\n")
        
        # Step 2: Extract fees with Bedrock
        fee_data = extract_fees_with_bedrock(markdown_text, card_name)
        
        if fee_data:
            result = {
                "card_name": card_name,
                "pricing_terms_url": pricing_url,
                **fee_data
            }
            results.append(result)
            log.info(f"✓ Successfully extracted fees for {card_name}")
        else:
            log.warning(f"✗ Failed to extract fees for {card_name}")
        
        # Small delay between requests
        time.sleep(2)
    
    # Print final results
    log.info("\n" + "="*80)
    log.info("FINAL EXTRACTED FEE DATA")
    log.info("="*80)
    print(json.dumps(results, indent=2))
    
    # Save results
    output_path = 'output/extracted_fees.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    log.info(f"\n✓ Results saved to {output_path}")
    log.info(f"✓ Successfully processed {len(results)}/{len(test_cards)} cards")


if __name__ == '__main__':
    main()
