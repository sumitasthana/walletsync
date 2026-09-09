# Edge Cases and Extraction Failures

**Generated:** 2026-04-21 17:11 UTC-04:00

---

## Category Validation Failures (12 cards)

### Root Cause
Claude 3 Haiku invents semantically accurate but schema-invalid category names despite strict enum constraints in the tool schema.

### Pattern
Co-branded cards with brand-specific spending categories are most affected.

---

## Failed Cards by Type

### Co-Branded Airline Cards (6 failures)

**Southwest Cards (3):**
- Southwest Rapid Rewards® Plus
- Southwest Rapid Rewards® Premier  
- Southwest Rapid Rewards® Priority

**Error:** Category `southwest_airlines` not in ALLOWED_CATEGORIES

**Expected behavior:** Should use `airlines` category with notes="Southwest Airlines purchases"

---

**IHG Cards (3):**
- IHG One Rewards Premier
- IHG One Rewards Traveler
- IHG One Rewards Premier Business

**Error:** Category `ihg` or `ihg_hotels` not in ALLOWED_CATEGORIES

**Expected behavior:** Should use `other` category with notes="IHG hotel purchases"

---

### Co-Branded Retail Cards (2 failures)

**DoorDash:**
- DoorDash Rewards Mastercard®

**Error:** Category `doordash` not in ALLOWED_CATEGORIES

**Expected behavior:** Should use `other` category with notes="DoorDash purchases"

---

**Amazon Cards (2 - HTML fallback):**
- Prime Visa
- Amazon Visa

**Error:** Category `amazon` not in ALLOWED_CATEGORIES

**Expected behavior:** Should use `other` category with notes="Amazon.com purchases"

**Note:** These failed in HTML fallback, not PDF extraction

---

### Business Cards (4 failures)

**Ink Series:**
- Ink Business Cash®
- Ink Business Preferred®
- Ink Business Premier®
- Ink Business Unlimited®

**Error:** Unknown (logs truncated, likely category validation)

**Hypothesis:** May be inventing `office_supplies`, `shipping`, `internet_cable_phone` or similar business-specific categories

**Expected behavior:** Should use standard categories (gas, dining, travel, etc.) with business context in notes

---

### Aeroplan Card (1 failure)

**Card:** Aeroplan® Card

**Error:** `redemption_options.0.value_cents_per_point` - Input should be a valid number, got None

**Root cause:** PDF likely states "value varies by airline partner" without baseline redemption value

**Fix needed:** Make `value_cents_per_point` nullable in schema for variable-value programs

---

## Business Card Pricing Format Issue (1 failure)

**Card:** Sapphire Reserve for BusinessSM

**Error:** Missing required field `cash_advance_apr`

**Root cause:** Business card Schumer Box may not disclose cash advance APR in same format as consumer cards

**Investigation needed:** Manual inspection of `output/raw/pricing/sapphire-reserve-5a3e5c.md`

**Possible fixes:**
1. Make `cash_advance_apr` optional for business cards
2. Add business card detection logic
3. Manual override for this specific card

---

## Patterns Observed

### Pattern 1: Brand-Specific Categories
**Trigger:** Card name contains brand (Southwest, IHG, DoorDash, Amazon)

**LLM behavior:** Creates category matching brand name

**Why it happens:** LLM prioritizes semantic accuracy over schema compliance

**Solution:** Add explicit mapping in prompt:
```
- Southwest Airlines purchases → use "airlines" category
- IHG hotel purchases → use "other" category with notes
- DoorDash purchases → use "other" category with notes
- Amazon purchases → use "other" category with notes
```

---

### Pattern 2: Business Card Differences
**Trigger:** Card name contains "Business" or "Ink"

**Observed differences:**
1. Pricing: Different Schumer Box format (missing cash advance APR)
2. Rewards: May have business-specific categories (office supplies, shipping, etc.)

**Solution:** Add business card detection and adjusted validation rules

---

### Pattern 3: Variable-Value Redemptions
**Trigger:** Transfer partner cards (Aeroplan, Chase Ultimate Rewards)

**Issue:** Redemption value varies by partner, no single baseline

**Current schema:** Requires non-null `value_cents_per_point`

**Solution:** Make field nullable, add `is_variable_value` boolean flag

---

## Recommendations

### Short-term (Manual Fixes)

1. **Post-process failed extractions:**
   - Load raw PDF text
   - Manually create JSON with correct categories
   - Use "other" category with descriptive notes

2. **Update ALLOWED_CATEGORIES:**
   - Add `amazon` (legitimate category for Amazon cards)
   - Add `southwest` or map to `airlines`
   - Add `doordash` or map to `other`

3. **Fix Sapphire Reserve for Business:**
   - Inspect dump file manually
   - Either add missing APR or make field optional

---

### Long-term (Systematic Fixes)

1. **Enhanced prompt with explicit mappings:**
```
BRAND-SPECIFIC CATEGORY MAPPINGS:
- Southwest Airlines → "airlines"
- IHG hotels → "other" with notes="IHG hotel purchases"
- DoorDash → "other" with notes="DoorDash purchases"
- Amazon → "other" with notes="Amazon.com purchases"
- Office supplies → "other" with notes="Office supply purchases"
```

2. **Schema updates:**
   - Make `value_cents_per_point` nullable
   - Make `cash_advance_apr` optional for business cards
   - Add `is_business_card` boolean flag

3. **Retry logic:**
```python
try:
    rewards = extract_rewards(pdf_text)
except ValidationError as e:
    if "not in ALLOWED_CATEGORIES" in str(e):
        # Retry with enhanced category mapping prompt
        rewards = extract_rewards_with_mapping(pdf_text)
```

4. **Category expansion:**
   - Add `amazon` to ALLOWED_CATEGORIES
   - Add `office_supplies` to ALLOWED_CATEGORIES
   - Add `shipping` to ALLOWED_CATEGORIES
   - Add `internet_cable_phone` to ALLOWED_CATEGORIES

---

## Testing Recommendations

Before re-running failed extractions:

1. **Test category mapping prompt** on 1-2 failed cards
2. **Verify schema changes** don't break existing extractions
3. **Add validation tests** for edge cases
4. **Document expected behavior** for each card type

---

## Cost to Fix

**Re-running 12 failed rewards extractions:**
- 12 cards × $0.003/card = **$0.036**

**Re-running 2 failed HTML fallback extractions:**
- 2 cards × $0.001/card = **$0.002**

**Total re-run cost: ~$0.04**

**Total project cost with fixes: ~$0.18** (well under $0.75 budget)

---

**Next Action:** Choose fix strategy (manual vs automated) and proceed with re-extraction
