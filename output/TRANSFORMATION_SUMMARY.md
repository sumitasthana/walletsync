# Data Transformation Summary

## Overview
Transformed 82 scraped Chase credit cards from messy HTML text into clean, structured JSON with typed fields.

## Schema Mapping

### Input → Output Transformations

| Field | Type | Transformation Logic |
|-------|------|---------------------|
| `card_name` | String | Cleaned and trimmed |
| `annual_fee_usd` | Integer | Parsed from text like "$95†" or "$0 intro then $150" → extracts standard fee |
| `waived_first_year` | Boolean | Detects patterns like "$0 intro annual fee for the first year, then $150" |
| `reward_currency` | String | Classified as "Cash Back", "Points", or "Miles" based on earning_rates text |
| `sign_up_bonus_value` | Integer | Extracted from "Earn 125,000 points" → 125000 or "Earn a $250 bonus" → 250 |
| `sign_up_bonus_spend_req` | Integer | Extracted from "...after you spend $6,000 on purchases" → 6000 |
| `sign_up_bonus_months` | Integer | Extracted from "...in the first 3 months" → 3 |
| `base_earn_rate` | Float | Parsed from "unlimited 1.5% cash back" → 1.5 or "1 point per $1" → 1.0 |
| `pricing_terms_url` | String | Passed through unchanged |
| `rewards_agreement_url` | String | Passed through unchanged |

## Parsing Examples

### Example 1: Chase Freedom Unlimited®
**Input:**
```
annual_fee: "ANNUAL FEE\n\n$0†"
offer_threshold: "Earn a $200 \nstrikethrough\n$250 bonus\n\nEarn a $250 bonus after you spend $500..."
earning_rates: "...unlimited 1.5% cash back..."
```

**Output:**
```json
{
  "annual_fee_usd": 0,
  "waived_first_year": false,
  "sign_up_bonus_value": 250,
  "sign_up_bonus_spend_req": 500,
  "sign_up_bonus_months": 3,
  "base_earn_rate": 1.5,
  "reward_currency": "Cash Back"
}
```

### Example 2: Chase Sapphire Reserve®
**Input:**
```
annual_fee: "ANNUAL FEE\n\n$795 annual fee†; $195 for each authorized user†"
offer_threshold: "Earn 125,000 points\n\nafter you spend $6,000 on purchases in the first 3 months..."
```

**Output:**
```json
{
  "annual_fee_usd": 795,
  "waived_first_year": false,
  "sign_up_bonus_value": 125000,
  "sign_up_bonus_spend_req": 6000,
  "sign_up_bonus_months": 3,
  "reward_currency": "Points"
}
```

### Example 3: United℠ Explorer Card
**Input:**
```
annual_fee: "ANNUAL FEE\n\n$0 intro annual fee for the first year, then $150†"
```

**Output:**
```json
{
  "annual_fee_usd": 150,
  "waived_first_year": true,
  "reward_currency": "Miles"
}
```

## Statistics

- **Total Cards:** 82
- **Cards with Sign-Up Bonuses:** 23 (28%)
- **Free Cards ($0 annual fee):** 55 (67%)
- **Cards with Waived First Year:** 1 (1%)
- **Average Annual Fee:** $77.50

### Reward Type Distribution
- **Cash Back:** 15 cards (18%)
- **Points:** 18 cards (22%)
- **Miles:** 9 cards (11%)
- **Unknown:** 40 cards (49%) - cards without clear earning structure in scraped text

## Files Generated

1. **`chase_cards.json`** (85 KB) - Raw scraped data
2. **`chase_cards_clean.json`** (9 KB) - Cleaned, structured data
3. **`src/clean_data.py`** - Transformation script with regex parsers

## Usage

```bash
# Run the data cleaning script
python src/clean_data.py

# Output: output/chase_cards_clean.json
```

## Notes

- All null values represent missing or unparseable data
- Base earn rates are only captured when explicitly stated for "all purchases"
- Some cards have complex tiered earning structures not captured in base_earn_rate
- The transformation is idempotent - running multiple times produces the same output
