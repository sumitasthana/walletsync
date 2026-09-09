# Data Quality Tiers - Contract for Downstream Consumers

## Overview

Every rewards extraction output includes a `data_quality_tier` field that indicates the source and completeness of the data.

## Tier Definitions

### Tier 1: PDF-Based Extraction (`tier_1_pdf`)

**Source:** Rewards Program Agreement PDF (legal document)

**Confidence:** High

**Schema:** `RewardsExtended`

**All fields available:**
- ✅ `earning_categories` - Full earning structure
- ✅ `redemption_options` - All redemption methods and values
- ✅ `point_value_cents_baseline` - Baseline cash redemption value
- ✅ `transfer_partners` - Airline/hotel transfer ratios
- ✅ `bonus_disqualifying_products` - Products that disqualify signup bonus
- ✅ `bonus_clawback_period_months` - Clawback period
- ✅ `points_expiration_months` - Expiration policy
- ✅ `redemption_minimum_usd` - Minimum redemption threshold
- ✅ `cardmember_anniversary_benefit` - Annual benefits

**Use cases:**
- Full rewards optimization
- Transfer partner analysis
- Redemption value calculations
- Signup bonus eligibility checks

**Example cards:**
- Chase Freedom Flex®
- Chase Freedom Rise®
- United℠ Explorer Card

---

### Tier 2: HTML Fallback Extraction (`tier_2_html`)

**Source:** Product page marketing copy

**Confidence:** Medium

**Schema:** `RewardsHtmlFallback`

**Available fields:**
- ✅ `earning_categories` - Earning structure (rates and categories)
- ✅ `cardmember_anniversary_benefit` - Annual benefits (if mentioned)

**Missing fields (explicitly marked in `fields_not_available`):**
- ❌ `redemption_options` - Not available in marketing copy
- ❌ `point_value_cents_baseline` - Not available in marketing copy
- ❌ `transfer_partners` - Not available in marketing copy
- ❌ `bonus_disqualifying_products` - Not available in marketing copy
- ❌ `bonus_clawback_period_months` - Not available in marketing copy
- ❌ `points_expiration_months` - Not available in marketing copy
- ❌ `redemption_minimum_usd` - Not available in marketing copy

**Use cases:**
- Earning rate comparisons
- Category bonus identification
- Basic card recommendations

**NOT suitable for:**
- Transfer partner analysis
- Redemption value calculations
- Expiration policy checks

**Example cards:**
- Chase Sapphire Reserve® ⚠️
- Chase Sapphire Preferred® ⚠️
- Marriott Bonvoy Boundless®
- IHG One Rewards Premier

---

### Tier 3: No Rewards Data (`tier_3_none`)

**Source:** N/A

**Reason:** No rewards program, extraction failed, or not yet processed

**Schema:** N/A (no rewards object present)

**Example cards:**
- Slate® (balance transfer card, no rewards program)
- Cards with failed extraction
- Cards not yet processed

---

## Usage Guidelines

### Filtering by Tier

```python
# Load rewards data
tier_1_cards = [c for c in rewards if c.get('data_quality_tier') == 'tier_1_pdf']
tier_2_cards = [c for c in rewards if c.get('data_quality_tier') == 'tier_2_html']

# Only use cards with transfer partner data
cards_with_transfers = [c for c in tier_1_cards if c.get('transfer_partners')]
```

### Checking Field Availability

```python
# Tier 2 cards explicitly list unavailable fields
if card.get('data_quality_tier') == 'tier_2_html':
    unavailable = card.get('fields_not_available', [])
    if 'transfer_partners' in unavailable:
        print("Transfer partner data not available for this card")
```

### Safe Field Access

```python
# Always check for null/empty before using
transfer_partners = card.get('transfer_partners', [])
if transfer_partners:
    # Safe to analyze transfer partners
    pass
else:
    # Either Tier 2 card or Tier 1 card with no partners
    pass
```

---

## Important Notes

### Flagship Cards in Tier 2

**Chase Sapphire Reserve® and Chase Sapphire Preferred®** are currently extracted via HTML fallback (Tier 2), despite being flagship premium cards. This means:

- ✅ Earning categories are accurate
- ❌ **Transfer partner data is missing** (critical for these cards)
- ❌ Redemption multipliers are missing

**Workaround:** Manually add transfer partner data for these cards, or enhance scraper to visit product detail pages.

### Do Not Assume Field Presence

Even Tier 1 cards may have null values for certain fields if the data genuinely doesn't exist (e.g., no transfer partners, no expiration policy).

**Always check for null/empty before using any field.**

---

## Schema Enforcement

The `data_quality_tier` field is:
- **Required** in all rewards extraction outputs
- **Immutable** (set at extraction time, not modifiable downstream)
- **Validated** by Pydantic schema

Downstream consumers can rely on this field to filter and process data appropriately.

---

**Last Updated:** 2026-04-21 15:55 UTC-04:00
