# Step 1: HTML Table Parsing — COMPLETE ✅

**Date:** 2026-04-21 18:18 UTC-04:00  
**Objective:** Replace markdownify with structured HTML table parsing

---

## Changes Made

### Rewritten: `src/dump_pricing_text.py`

**Before:**
```
Pricing HTML → markdownify → markdown text → write .md file
```

**After:**
```
Pricing HTML → BeautifulSoup → {label: value} dict → write .json file
```

### Key Functions Added

1. **`extract_schumer_rows(html)`** - Parse all table rows into label→value dict
2. **`extract_full_text(html)`** - Extract plain text fallback
3. **`validate_dump(rows, card_id)`** - Check for required Schumer Box rows
4. **`scrape_pricing_page_to_json()`** - Main scraping function returning structured dict

### Output Format Changed

**Old:** `output/raw/pricing/{card_id}.md` (markdown with YAML frontmatter)

**New:** `output/raw/pricing/{card_id}.json` (structured JSON)

```json
{
  "card_id": "freedom-unlimited-3f087d",
  "card_name": "Chase Freedom Unlimited®",
  "pricing_terms_url": "https://...",
  "dumped_at": "2026-04-21T22:15:11.687595+00:00",
  "schumer_rows": {
    "Purchase Annual Percentage Rate (APR)": "0% Intro APR...",
    "Cash Advance APR": "28.49%...",
    "Annual Membership Fee": "None",
    ...
  },
  "full_page_text": "...",
  "dump_warnings": ["Missing expected rows: ..."]  // optional
}
```

---

## Execution Results

### Full Run: 41/41 Cards ✅

```
✓ Dumped: 41
⊘ Skipped: 0
✗ Failed: 0
```

**Time:** ~2 minutes  
**Cost:** $0 (no LLM calls)

### Validation Results

All 41 cards have the 5 required Schumer Box row categories:
- ✅ Annual (Membership Fee)
- ✅ Foreign Transaction
- ✅ Late Payment
- ✅ Cash Advance (fee row)
- ✅ Balance Transfer

**Note:** Sapphire Reserve for Business missing "Balance Transfer" row (business card doesn't offer balance transfers)

---

## Critical Finding: Sapphire Reserve for Business

**Card:** Sapphire Reserve for BusinessSM  
**Previous failure:** Missing `cash_advance_apr` field in LLM extraction

**Root cause discovered:** The source HTML **does not have a "Cash Advance APR" row**

### Actual Schumer Box Structure (Business Card)

```json
{
  "Flex for Business Annual Percentage Rate (APR)": "17.74% to 28.49%...",
  "Grace Period": "Your due date will be...",
  "Minimum Interest Charge": "None",
  "Annual Membership Fee": "$795",
  "Cash Advances": "Either $15 or 5%...",  // FEE only, no APR
  "Foreign Transactions": "None",
  "Late Payment": "$40 or 2%..."
}
```

**Missing rows:**
- ❌ Cash Advance APR (not disclosed separately)
- ❌ Balance Transfer APR
- ❌ Balance Transfer fee
- ❌ Penalty APR

### Comparison: Consumer vs Business Cards

**Consumer cards (e.g., Freedom Unlimited):**
- Purchase APR
- Balance Transfer APR
- **Cash Advance APR** ✅
- Penalty APR
- My Chase Loan APR

**Business cards (e.g., Sapphire Reserve for Business):**
- **Flex for Business APR** (single APR for all transactions)
- No separate Cash Advance APR ❌
- No Balance Transfer options ❌

### Implication for Path B

The deterministic parser **cannot extract a field that doesn't exist**. 

**Options:**
1. Make `cash_advance_apr` **optional** in `PricingExtended` schema
2. Add business card detection and use different schema
3. Infer cash advance APR from "Flex for Business APR" range (use max value)
4. Leave field as null for business cards

**Recommended:** Option 3 - Use the max of "Flex for Business APR" range as cash advance APR for business cards

---

## Spot Check Results

### 1. Freedom Unlimited (Consumer, Simple) ✅

- **Rows:** 17
- **Has Cash Advance APR:** ✅ Yes
- **Warnings:** None
- **Structure:** Standard consumer Schumer Box

### 2. Sapphire Reserve (Consumer, Premium) ✅

- **Rows:** 16
- **Has Cash Advance APR:** ✅ Yes
- **Warnings:** None
- **Structure:** Standard consumer Schumer Box with $550 annual fee

### 3. Sapphire Reserve for Business (Business, Previously Broken) ✅

- **Rows:** 7 (much simpler than consumer cards)
- **Has Cash Advance APR:** ❌ No (not in source)
- **Warnings:** Missing Balance Transfer
- **Structure:** Business card format with "Flex for Business APR"

---

## Files Created

### New JSON Dumps
- `output/raw/pricing/*.json` - 41 structured JSON dumps

### Preserved Backups
- `output/raw/pricing_markdown_backup/*.md` - 41 markdown dumps (backup)

### Modified Scripts
- `src/dump_pricing_text.py` - Rewritten for HTML table parsing

---

## Validation Summary

**Required rows check:**
- 41/41 cards have "Annual" (Membership Fee)
- 41/41 cards have "Foreign Transaction"
- 41/41 cards have "Late Payment"
- 41/41 cards have "Cash Advance" (fee)
- 40/41 cards have "Balance Transfer" (business cards excluded)

**Warnings:**
- 1 card (Sapphire Reserve for Business) missing Balance Transfer - **expected for business cards**

---

## Next Steps

**Step 2:** Write deterministic field extractors

**Approach:**
1. Create field extractor functions (regex on cell values)
2. Handle consumer vs business card differences
3. Extract numeric values from text (e.g., "18.24% to 27.74%" → min=18.24, max=27.74)
4. Handle intro APR periods (e.g., "0% for 15 months" → intro_pct=0, intro_months=15)
5. Validate against baseline fixtures

**Expected outcome:**
- 41/41 pricing extraction (vs 40/41 baseline)
- Deterministic output (no LLM randomness)
- Unit-testable extractors

---

**Status:** ✅ COMPLETE

**Ready for:** Step 2 - Deterministic field extractors
