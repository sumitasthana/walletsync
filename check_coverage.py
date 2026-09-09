"""Quick script to check extraction coverage."""
import json

# Load data
cards = json.load(open('output/chase_cards_clean.json'))
pricing = json.load(open('output/extracted_pricing_extended.json'))
rewards_pdf = json.load(open('output/extracted_rewards_extended.json'))
rewards_html = json.load(open('output/extracted_rewards_html_fallback.json'))

# Extract IDs
pricing_ids = {p['card_id'] for p in pricing if 'card_id' in p}
rewards_pdf_ids = {r['card_id'] for r in rewards_pdf if 'card_id' in r}
rewards_html_ids = {r['card_id'] for r in rewards_html if 'card_id' in r}

# Find cards with no rewards
no_rewards = [c for c in cards if c['card_id'] not in rewards_pdf_ids and c['card_id'] not in rewards_html_ids]

print(f"Total cards: {len(cards)}")
print(f"Pricing extracted: {len(pricing_ids)}")
print(f"Rewards PDF: {len(rewards_pdf_ids)}")
print(f"Rewards HTML: {len(rewards_html_ids)}")
print(f"No rewards: {len(no_rewards)}")
print("\nCards with no rewards data:")
for c in no_rewards:
    print(f"  - {c['card_name']}")
