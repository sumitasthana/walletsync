# WalletSync Extraction Coverage Report

**Generated:** 2026-04-21 22:35 UTC-04:00  
**Status:** Full production run complete with deterministic pricing extraction

---

## Current Coverage

**Total unique cards:** 41

### Pricing Extraction (Deterministic - Path B)

**Extraction Method:** Deterministic HTML table parsing (replaced LLM as of 2026-04-21)

- **Cards with pricing data:** 41/41 (100%) ✅
- **Failed:** 0
- **Extraction time:** <1 second (vs ~5 minutes LLM)
- **Cost:** $0 (vs ~$0.07 LLM)
- **Hallucinations:** 0 (vs 3 LLM hallucinations corrected)

**Key improvements over LLM:**
- ✅ **Sapphire Reserve for Business℠** - Now successfully extracted (was failed in LLM)
- ✅ **Zero hallucinations** - LLM invented 3 balance transfer intro offers that didn't exist
- ✅ **100% reproducible** - Same input always produces same output
- ✅ **Unit-testable** - 39 tests ensure format changes break build loudly

**Technical details:** See `PATH_B_COMPLETE.md` for migration documentation

### Rewards Extraction

**Tier 1 - PDF Path (RewardsExtended):**
- **Cards extracted:** 13/41 (32%)
- **Success rate from PDFs:** 13/25 (52%)
- **Failed:** 12 (category validation errors)

**Tier 2 - HTML Fallback Path (RewardsHtmlFallback):**
- **Cards extracted:** 13/41 (32%)
- **Success rate from eligible:** 13/15 (87%)
- **Failed:** 2 (Amazon cards - category validation)

**Total cards with rewards data:** 26/41 (63%)

### Cards with No Rewards Data: 15/41 (37%)

**Reason: Balance transfer card (no rewards program)**
- Slate®

**Reason: PDF extraction failed (LLM category validation errors)**
- United Gateway℠ Card (likely invalid category)
- United Club℠ Card (likely invalid category)
- Southwest Rapid Rewards® Plus (invalid category "southwest_airlines")
- Southwest Rapid Rewards® Premier (invalid category "southwest_airlines")
- World of Hyatt (likely invalid category)
- Aeroplan® Card (null redemption value error)
- DoorDash Rewards Mastercard® (invalid category "doordash")
- Ink Business Preferred® (likely business-specific category)
- Ink Business Cash® (likely business-specific category)
- Southwest Rapid Rewards® Premier Business (likely invalid category)
- IHG One Rewards Premier Business (likely invalid category)
- World of Hyatt Business (likely invalid category)

**Reason: HTML fallback extraction failed (LLM category validation errors)**
- Prime Visa (invalid category "amazon")
- Amazon Visa (invalid category "amazon")

---

## Known MVP Limitations

### 1. HTML Fallback Cards Have Partial Rewards Data

Cards extracted via HTML fallback (Tier 2) are **missing the following fields**:
- `redemption_options` (cash back value, transfer partners, travel portal multipliers)
- `point_value_cents_baseline` (baseline redemption value)
- `transfer_partners` (airline/hotel transfer ratios)
- `bonus_disqualifying_products` (which cards disqualify you from sign-up bonus)
- `bonus_clawback_period_months` (how long before you can cancel without penalty)
- `points_expiration_months` (when points expire)
- `redemption_minimum_usd` (minimum redemption threshold)

These fields require the legal Rewards Program Agreement PDF, which is not available for all cards.

### 2. Flagship Cards Use HTML Fallback

**Chase Sapphire Reserve® and Chase Sapphire Preferred®** are extracted via HTML fallback (Tier 2), despite being flagship premium cards. This means:
- ✅ Earning categories are captured
- ❌ Transfer partner data is missing (critical for these cards)
- ❌ Redemption multipliers are missing

**Root cause:** RPA PDF links are not present on the product listing page; scraper would need to visit individual product detail pages to find them.

### 3. Transfer Partner Data Only Available for Tier 1 Cards

Transfer partners (airline/hotel loyalty programs) are only extracted for cards with RPA PDFs. This affects:
- Chase Sapphire Reserve® (HTML fallback - missing transfer partners)
- Chase Sapphire Preferred® (HTML fallback - missing transfer partners)
- All co-branded airline/hotel cards without RPA PDFs

### 4. Test Run Incomplete

**Only 3 cards have been fully processed through the pricing + rewards PDF pipeline:**
- Chase Freedom Flex®
- Chase Freedom Unlimited® (pricing only)
- United℠ Explorer Card

**Remaining 38 cards need full extraction run.**

---

## Data Quality Tiers

### Tier 1: PDF-Based Extraction (`tier_1_pdf`)
- **Source:** Rewards Program Agreement PDF
- **Confidence:** High
- **Fields:** All fields available
- **Cards:** 3 (Freedom Flex, Freedom Rise, United Explorer)

### Tier 2: HTML Fallback Extraction (`tier_2_html`)
- **Source:** Product page marketing copy
- **Confidence:** Medium
- **Fields:** Earning categories only
- **Missing:** Redemption options, transfer partners, expiration rules
- **Cards:** 12 (Sapphire Reserve, Sapphire Preferred, Marriott, IHG, Disney, etc.)

### Tier 3: No Rewards Data (`tier_3_none`)
- **Source:** N/A
- **Reason:** No rewards program, extraction failed, or not yet processed
- **Cards:** 26

---

## Expected Full-Run Coverage

**After processing all 41 cards:**

| Tier | Expected Count | Percentage |
|------|----------------|------------|
| Tier 1 (PDF) | ~25 | 61% |
| Tier 2 (HTML) | ~11 | 27% |
| Tier 3 (None) | ~5 | 12% |
| **Total** | **41** | **100%** |

**Tier 1 + Tier 2 combined coverage: ~88%**

---

## Recommendations

### For Downstream Consumers

1. **Filter by `data_quality_tier` field** to distinguish PDF vs HTML extraction
2. **Do not assume transfer partner data exists** - check for null/empty arrays
3. **Tier 2 cards are suitable for earning rate comparisons only** - not for redemption analysis
4. **Tier 1 cards are suitable for full rewards optimization** - all fields available

### For Further Development

1. **Enhance scraper to visit product detail pages** - would recover more RPA PDFs
2. **Add retry logic for HTML fallback validation errors** - would recover 3 failed Disney/Amazon cards
3. **Manual data entry for flagship cards** - Sapphire Reserve/Preferred deserve Tier 1 data
4. **Complete full extraction run** - process remaining 38 cards

---

## Files

- **Pricing data:** `output/extracted_pricing_extended.json` (41 cards, deterministic)
- **Pricing raw dumps:** `output/raw/pricing/*.json` (41 structured JSON dumps)
- **Rewards PDF data:** `output/extracted_rewards_extended.json` (13 cards, LLM)
- **Rewards HTML data:** `output/extracted_rewards_html_fallback.json` (13 cards, LLM)
- **Unified dataset:** `output/unified_card_data.json` (combined pricing + rewards)

---

## Cost Analysis

**Per full extraction run:**

| Component | Method | Cost | Time |
|-----------|--------|------|------|
| **Pricing** | Deterministic (Path B) | $0 | <1 sec |
| **Rewards PDF** | LLM (Bedrock) | ~$0.04 | ~2 min |
| **Rewards HTML** | LLM (Bedrock) | ~$0.01 | ~30 sec |
| **Total** | Hybrid | **~$0.05** | **~3 min** |

**Before Path B:** ~$0.12 per run (pricing + rewards)  
**After Path B:** ~$0.05 per run (rewards only)  
**Savings:** 58% cost reduction

---

**Last Updated:** 2026-04-21 22:35 UTC-04:00
