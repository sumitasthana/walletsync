"""Generate per-card pricing fixtures for regression testing."""
import json
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load current LLM-extracted pricing data
data = json.load(open('data/extracted_pricing_extended.json'))

# Filter out metadata records and failed cards
cards = [card for card in data if 'card_id' in card]

# Create fixture for each card
os.makedirs('tests/fixtures/pricing', exist_ok=True)
for card in cards:
    cid = card['card_id']
    fixture_path = f'tests/fixtures/pricing/{cid}.json'
    with open(fixture_path, 'w', encoding='utf-8') as f:
        json.dump(card, f, indent=2, ensure_ascii=False)

print(f'✓ Wrote {len(cards)} pricing fixtures to tests/fixtures/pricing/')
print(f'  Cards: {", ".join([c["card_name"] for c in cards[:3]])}...')
