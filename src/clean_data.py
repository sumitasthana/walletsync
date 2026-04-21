"""Clean and transform scraped Chase card data to structured schema."""

import json
import re
from typing import Optional


def extract_annual_fee(fee_text: Optional[str]) -> tuple[int, bool]:
    """
    Extract annual fee amount and whether it's waived first year.
    Returns: (annual_fee_usd, waived_first_year)
    """
    if not fee_text:
        return (0, False)
    
    fee_text = fee_text.upper()
    
    # Check for intro/first year waiver patterns
    waived_first_year = bool(
        re.search(r'\$0\s+INTRO', fee_text) or
        re.search(r'INTRO.*\$0', fee_text) or
        re.search(r'\$0.*FIRST YEAR', fee_text) or
        re.search(r'FIRST YEAR.*\$0', fee_text)
    )
    
    # Extract all dollar amounts
    amounts = re.findall(r'\$(\d+(?:,\d{3})*)', fee_text)
    amounts = [int(amt.replace(',', '')) for amt in amounts]
    
    if not amounts:
        return (0, False)
    
    # If waived first year, get the non-zero fee
    if waived_first_year:
        non_zero = [amt for amt in amounts if amt > 0]
        return (non_zero[0] if non_zero else 0, True)
    
    # Otherwise return the first/main fee
    return (amounts[0], False)


def classify_reward_currency(earning_text: Optional[str]) -> str:
    """Classify reward type based on earning rates text."""
    if not earning_text:
        return "Unknown"
    
    text_lower = earning_text.lower()
    
    # Check for miles
    if 'mile' in text_lower or 'avios' in text_lower:
        return "Miles"
    
    # Check for points
    if 'point' in text_lower:
        return "Points"
    
    # Check for cash back
    if 'cash back' in text_lower or 'cashback' in text_lower or '%' in text_lower:
        return "Cash Back"
    
    return "Unknown"


def extract_sign_up_bonus(offer_text: Optional[str]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Extract sign-up bonus details.
    Returns: (bonus_value, spend_requirement, months)
    """
    if not offer_text:
        return (None, None, None)
    
    bonus_value = None
    spend_req = None
    months = None
    
    # Extract bonus value
    # Pattern 1: "Earn 125,000 points"
    match = re.search(r'earn\s+(\d+(?:,\d{3})*)\s+(?:bonus\s+)?(?:points|miles|avios)', offer_text, re.IGNORECASE)
    if match:
        bonus_value = int(match.group(1).replace(',', ''))
    else:
        # Pattern 2: "Earn a $250 bonus"
        match = re.search(r'earn\s+a?\s*\$(\d+(?:,\d{3})*)\s+bonus', offer_text, re.IGNORECASE)
        if match:
            bonus_value = int(match.group(1).replace(',', ''))
    
    # Extract spend requirement
    match = re.search(r'spend\s+\$(\d+(?:,\d{3})*)', offer_text, re.IGNORECASE)
    if match:
        spend_req = int(match.group(1).replace(',', ''))
    
    # Extract time limit in months
    match = re.search(r'(?:first|within)\s+(\d+)\s+months?', offer_text, re.IGNORECASE)
    if match:
        months = int(match.group(1))
    
    return (bonus_value, spend_req, months)


def extract_base_earn_rate(earning_text: Optional[str]) -> Optional[float]:
    """Extract the base earning rate for non-categorized spend."""
    if not earning_text:
        return None
    
    text_lower = earning_text.lower()
    
    # Pattern 1: "unlimited 1.5% cash back" or "earn 1.5% cash back"
    match = re.search(r'(?:unlimited|earn)\s+(\d+(?:\.\d+)?)\s*%', text_lower)
    if match:
        return float(match.group(1))
    
    # Pattern 2: "1% on all other purchases"
    match = re.search(r'(\d+(?:\.\d+)?)\s*%\s+(?:cash back\s+)?on\s+all\s+(?:other\s+)?purchases', text_lower)
    if match:
        return float(match.group(1))
    
    # Pattern 3: "Earn 1 point/mile for every $1" or "1x on all purchases"
    match = re.search(r'(?:earn\s+)?(\d+(?:\.\d+)?)\s*(?:x|point|mile|avios)(?:s)?\s+(?:for\s+every\s+\$1|on\s+all)', text_lower)
    if match:
        return float(match.group(1))
    
    # Pattern 4: "1.5% cash back on all purchases"
    match = re.search(r'(\d+(?:\.\d+)?)\s*%.*?on\s+all\s+purchases', text_lower)
    if match:
        return float(match.group(1))
    
    return None


def clean_card_data(raw_card: dict) -> dict:
    """Transform raw scraped card data to clean schema."""
    
    # Extract annual fee info
    annual_fee, waived = extract_annual_fee(raw_card.get('annual_fee'))
    
    # Classify reward currency
    reward_currency = classify_reward_currency(raw_card.get('earning_rates'))
    
    # Extract sign-up bonus details
    bonus_value, spend_req, months = extract_sign_up_bonus(raw_card.get('offer_threshold'))
    
    # Extract base earning rate
    base_rate = extract_base_earn_rate(raw_card.get('earning_rates'))
    
    return {
        'card_name': raw_card.get('card_name', '').strip(),
        'annual_fee_usd': annual_fee,
        'waived_first_year': waived,
        'reward_currency': reward_currency,
        'sign_up_bonus_value': bonus_value,
        'sign_up_bonus_spend_req': spend_req,
        'sign_up_bonus_months': months,
        'base_earn_rate': base_rate,
        'pricing_terms_url': raw_card.get('pricing_terms_url'),
        'rewards_agreement_url': raw_card.get('rewards_agreement_url')
    }


def main():
    # Load raw data
    with open('output/chase_cards.json', 'r', encoding='utf-8') as f:
        raw_cards = json.load(f)
    
    # Clean each card
    cleaned_cards = [clean_card_data(card) for card in raw_cards]
    
    # Save cleaned data
    output_path = 'output/chase_cards_clean.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_cards, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Cleaned {len(cleaned_cards)} cards")
    print(f"✓ Saved to {output_path}")
    
    # Print sample
    print("\n--- Sample Cleaned Card ---")
    print(json.dumps(cleaned_cards[0], indent=2))
    
    # Print statistics
    print("\n--- Statistics ---")
    print(f"Cards with sign-up bonus: {sum(1 for c in cleaned_cards if c['sign_up_bonus_value'])}")
    print(f"Cards with waived first year fee: {sum(1 for c in cleaned_cards if c['waived_first_year'])}")
    print(f"Average annual fee: ${sum(c['annual_fee_usd'] for c in cleaned_cards) / len(cleaned_cards):.2f}")
    print(f"\nReward types:")
    for rtype in ['Cash Back', 'Points', 'Miles']:
        count = sum(1 for c in cleaned_cards if c['reward_currency'] == rtype)
        print(f"  {rtype}: {count}")


if __name__ == '__main__':
    main()
