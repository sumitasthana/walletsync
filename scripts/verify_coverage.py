"""Verify extraction coverage after full run."""
import json
import os
from collections import Counter

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load all extraction outputs
pricing = json.load(open('data/chase/extracted_pricing_extended.json'))
rewards_pdf = json.load(open('data/chase/extracted_rewards_extended.json'))
rewards_html = json.load(open('data/chase/extracted_rewards_html_fallback.json'))

# Extract card records (skip metadata)
pricing_cards = [p for p in pricing if 'card_id' in p]
rewards_pdf_cards = [r for r in rewards_pdf if 'card_id' in r]
rewards_html_cards = [r for r in rewards_html if 'card_id' in r]

# Count by tier
tiers = Counter()
for card in rewards_pdf_cards:
    tiers[card.get('data_quality_tier', 'missing')] += 1
for card in rewards_html_cards:
    tiers[card.get('data_quality_tier', 'missing')] += 1

print(f"Total outputs: {len(pricing_cards)} pricing, {len(rewards_pdf_cards)} rewards PDF, {len(rewards_html_cards)} rewards HTML")
print(f"\nPricing coverage: {len(pricing_cards)}/41 ({len(pricing_cards)/41*100:.1f}%)")
print(f"Rewards PDF coverage: {len(rewards_pdf_cards)}/25 ({len(rewards_pdf_cards)/25*100:.1f}%)")
print(f"Rewards HTML coverage: {len(rewards_html_cards)}/15 ({len(rewards_html_cards)/15*100:.1f}%)")
print(f"Total rewards coverage: {len(rewards_pdf_cards) + len(rewards_html_cards)}/41 ({(len(rewards_pdf_cards) + len(rewards_html_cards))/41*100:.1f}%)")

print(f"\nTier breakdown:")
for tier, count in sorted(tiers.items()):
    print(f"  {tier}: {count}")

print(f"\nExpected vs Actual:")
print(f"  Expected tier_1_pdf: ~25, Actual: {tiers.get('tier_1_pdf', 0)}")
print(f"  Expected tier_2_html: ~9, Actual: {tiers.get('tier_2_html', 0)}")
print(f"  Expected tier_3_none: ~1, Actual: {41 - len(rewards_pdf_cards) - len(rewards_html_cards)}")

# List cards with no rewards data
all_cards = json.load(open('data/chase/cards_clean.json'))
rewards_pdf_ids = {r['card_id'] for r in rewards_pdf_cards}
rewards_html_ids = {r['card_id'] for r in rewards_html_cards}
no_rewards = [c for c in all_cards if c['card_id'] not in rewards_pdf_ids and c['card_id'] not in rewards_html_ids]

print(f"\nCards with no rewards data ({len(no_rewards)}):")
for card in no_rewards[:20]:  # Limit to first 20
    print(f"  - {card['card_name']}")
if len(no_rewards) > 20:
    print(f"  ... and {len(no_rewards) - 20} more")
