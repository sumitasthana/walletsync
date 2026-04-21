"""Extract reward constraints from PDF agreements using AWS Bedrock."""

import json
import logging
import os
import sys
import time
from io import BytesIO
from typing import Optional

import boto3
import fitz  # PyMuPDF
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def download_and_extract_pdf_text(url: str) -> Optional[str]:
    """
    Download PDF from URL and extract all text.
    
    Args:
        url: The rewards_agreement_url to download
        
    Returns:
        Extracted text from PDF, or None if failed
    """
    log.info(f"Downloading PDF: {url}")
    
    try:
        # Download PDF with standard User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Read PDF from bytes
        pdf_stream = BytesIO(response.content)
        
        # Extract text using PyMuPDF
        pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
        
        all_text = []
        page_count = pdf_document.page_count
        
        for page_num in range(page_count):
            page = pdf_document[page_num]
            text = page.get_text()
            all_text.append(text)
        
        # Combine all pages before closing
        full_text = "\n".join(all_text)
        
        # Close document after extraction
        pdf_document.close()
        
        # Clean text - remove excessive whitespace
        # Replace multiple newlines with double newline
        import re
        cleaned_text = re.sub(r'\n{3,}', '\n\n', full_text)
        # Replace multiple spaces with single space
        cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)
        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in cleaned_text.split('\n')]
        cleaned_text = '\n'.join(lines)
        
        log.info(f"Extracted {len(cleaned_text)} characters from {page_count} pages")
        
        return cleaned_text
        
    except Exception as e:
        log.error(f"Failed to download/extract PDF from {url}: {e}")
        return None


def extract_rules_with_bedrock(pdf_text: str, card_name: str) -> Optional[dict]:
    """
    Extract reward constraints from PDF text using AWS Bedrock Claude 3 Haiku.
    
    Args:
        pdf_text: The extracted text from the rewards agreement PDF
        card_name: Name of the card for logging
        
    Returns:
        Dictionary with extracted reward rules, or None if failed
    """
    log.info(f"Extracting reward rules for {card_name} using Bedrock...")
    
    try:
        # Initialize Bedrock Runtime client
        region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        bedrock = boto3.client('bedrock-runtime', region_name=region)
        
        # Define the tool for structured extraction
        tool_config = {
            "tools": [
                {
                    "toolSpec": {
                        "name": "extract_reward_constraints",
                        "description": "Extract reward program constraints and rules from a credit card rewards agreement document",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "category_exclusions": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Array of specific merchants, MCCs, or purchase types explicitly excluded from earning rewards or bonuses. Examples: 'Walmart', 'Target', 'gift cards', 'cash equivalents', 'balance transfers', 'cash advances'. Look in the Exclusions section and footnotes."
                                    },
                                    "point_expiration_policy": {
                                        "type": "string",
                                        "description": "The exact condition under which points expire (e.g., 'after 24 months of account inactivity'). Return null if points do not expire."
                                    },
                                    "redemption_minimum_usd": {
                                        "type": "integer",
                                        "description": "The minimum dollar value required to initiate a redemption. Return null if there is no minimum."
                                    },
                                    "bonus_eligibility_rule": {
                                        "type": "string",
                                        "description": "Rules preventing sign-up bonus abuse (e.g., 'Not available if you received a bonus in the last 48 months' or 'One bonus per account'). Return null if not specified."
                                    }
                                },
                                "required": [
                                    "category_exclusions",
                                    "point_expiration_policy",
                                    "redemption_minimum_usd",
                                    "bonus_eligibility_rule"
                                ]
                            }
                        }
                    }
                }
            ]
        }
        
        # Construct the prompt
        user_message = f"""You are analyzing a credit card rewards program agreement document. 
Extract the following reward constraints and invoke the extract_reward_constraints tool:

1. **category_exclusions** (ARRAY of STRINGS): Find ALL merchants, merchant categories, or purchase types that are EXCLUDED from earning rewards or bonuses.
   - Look in sections titled "Exclusions", "What doesn't earn rewards", "Restrictions", or in footnotes
   - Common exclusions: specific retailers (Walmart, Target), gift cards, cash equivalents, balance transfers, cash advances, fees
   - Return an empty array [] ONLY if the document explicitly states there are no exclusions
   - Be thorough - check footnotes and fine print

2. **point_expiration_policy** (STRING): Find the exact condition under which points/cash back expire.
   - Example: "Points expire after 24 months of account inactivity"
   - Example: "Cash back does not expire"
   - Return null if points do not expire

3. **redemption_minimum_usd** (INTEGER): Find the minimum dollar value to redeem.
   - Example: "$25 minimum for statement credit" → 25
   - Return null if there is no minimum

4. **bonus_eligibility_rule** (STRING): Find rules about sign-up bonus eligibility.
   - Example: "Not available if you received a new cardmember bonus in the last 48 months"
   - Example: "Limit one bonus per account"
   - Return null if not specified

IMPORTANT:
- Read the ENTIRE document including footnotes and fine print
- Pay special attention to sections on "Exclusions", "Limitations", "Restrictions"
- For category_exclusions, be comprehensive - list ALL excluded categories mentioned
- Use exact quotes from the document when possible

Here is the rewards agreement document:

{pdf_text}

Extract these four fields and call the extract_reward_constraints tool."""
        
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
                    if tool_use.get('name') == 'extract_reward_constraints':
                        rules_data = tool_use.get('input', {})
                        log.info(f"Successfully extracted rules for {card_name}")
                        return rules_data
            
            log.warning(f"Tool use response but no extract_reward_constraints found for {card_name}")
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
    
    # Filter for cards with PDF rewards agreement URLs
    cards_with_pdf = [
        c for c in cards 
        if c.get('rewards_agreement_url') and 
        '.pdf' in c.get('rewards_agreement_url').lower()
    ]
    log.info(f"Found {len(cards_with_pdf)} cards with PDF rewards agreements")
    
    # Take first 3 as test batch
    test_cards = cards_with_pdf[:3]
    log.info(f"Processing {len(test_cards)} test cards")
    
    results = []
    
    for idx, card in enumerate(test_cards, 1):
        card_name = card.get('card_name', 'Unknown')
        rewards_url = card.get('rewards_agreement_url')
        
        log.info(f"\n{'='*80}")
        log.info(f"Processing card {idx}/{len(test_cards)}: {card_name}")
        log.info(f"{'='*80}")
        
        # Step 1: Download and extract PDF text
        pdf_text = download_and_extract_pdf_text(rewards_url)
        
        if not pdf_text:
            log.error(f"Failed to extract PDF text for {card_name}")
            continue
        
        # Print first 1000 chars of PDF text for verification (first card only)
        if idx == 1:
            log.info("\n" + "="*80)
            log.info("RAW PDF TEXT OUTPUT (First Card - First 1000 chars)")
            log.info("="*80)
            print(pdf_text[:1000])
            log.info("="*80 + "\n")
        
        # Step 2: Extract rules with Bedrock
        rules_data = extract_rules_with_bedrock(pdf_text, card_name)
        
        if rules_data:
            result = {
                "card_name": card_name,
                "rewards_agreement_url": rewards_url,
                **rules_data
            }
            results.append(result)
            log.info(f"✓ Successfully extracted rules for {card_name}")
            log.info(f"  Category exclusions found: {len(rules_data.get('category_exclusions', []))}")
        else:
            log.warning(f"✗ Failed to extract rules for {card_name}")
        
        # Small delay between requests
        time.sleep(2)
    
    # Print final results
    log.info("\n" + "="*80)
    log.info("FINAL EXTRACTED REWARD RULES")
    log.info("="*80)
    print(json.dumps(results, indent=2))
    
    # Save results
    output_path = 'output/extracted_reward_rules.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    log.info(f"\n✓ Results saved to {output_path}")
    log.info(f"✓ Successfully processed {len(results)}/{len(test_cards)} cards")
    
    # Verification step
    log.info("\n" + "="*80)
    log.info("VERIFICATION NOTES")
    log.info("="*80)
    for result in results:
        exclusions = result.get('category_exclusions', [])
        log.info(f"\n{result['card_name']}:")
        log.info(f"  - Category exclusions: {len(exclusions)}")
        if len(exclusions) == 0:
            log.warning(f"  ⚠ WARNING: No exclusions found. Check if PDF footnotes were extracted.")
        else:
            log.info(f"  - Examples: {', '.join(exclusions[:3])}")


if __name__ == '__main__':
    main()
