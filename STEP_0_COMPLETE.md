# Step 0: Baseline Snapshot — COMPLETE ✅

**Date:** 2026-04-21 18:01 UTC-04:00  
**Objective:** Capture current LLM pricing extraction as regression baseline before Path B rewrite

---

## Actions Completed

### 1. Copied Full Baseline ✅
```bash
cp output/extracted_pricing_extended.json output/baseline_pricing_llm.json
```

**Result:** Master baseline file created

### 2. Generated Per-Card Fixtures ✅
```bash
mkdir -p tests/fixtures/pricing
python create_pricing_fixtures.py
```

**Result:** 40 individual JSON fixtures created

### 3. Backed Up Markdown Dumps ✅
```bash
cp -r output/raw/pricing output/raw/pricing_markdown_backup
```

**Result:** 41 markdown files preserved

---

## Verification Results

✅ **40 fixtures** in `tests/fixtures/pricing/`  
✅ **baseline_pricing_llm.json** exists and matches source size  
✅ **41 markdown dumps** backed up to `pricing_markdown_backup/`

### Sample Fixture Verified

`@tests/fixtures/pricing/freedom-flex-a6950e.json`:
- Contains all 23 PricingExtended fields
- Numeric values properly typed (float, int, null)
- Metadata fields present (card_id, card_name, pricing_terms_url)
- Ready for regression testing

---

## Baseline Coverage

**Cards in baseline:** 40/41 (98%)

**Excluded:**
- Sapphire Reserve for BusinessSM (failed - missing `cash_advance_apr`)

**Included:**
- All successfully extracted consumer cards
- All successfully extracted business cards (except Sapphire Reserve for Business)
- All card types (cash back, travel, co-branded)

---

## Path B Success Criteria

The new deterministic parser must:

1. ✅ **Match baseline** - Extract all 40 cards with identical or better accuracy
2. ✅ **Fix failure** - Successfully extract Sapphire Reserve for Business (41/41)
3. ✅ **Eliminate LLM cost** - No Bedrock calls for pricing extraction
4. ✅ **Be deterministic** - Same HTML → same output every time
5. ✅ **Be testable** - Unit tests for each field extractor

---

## Files Created

### Baseline Data
- `output/baseline_pricing_llm.json` - Master baseline (40 cards)
- `tests/fixtures/pricing/*.json` - 40 per-card fixtures

### Backups
- `output/raw/pricing_markdown_backup/*.md` - 41 markdown dumps

### Documentation
- `BASELINE_SNAPSHOT.md` - Detailed baseline documentation
- `create_pricing_fixtures.py` - Fixture generation script
- `STEP_0_COMPLETE.md` - This file

---

## Next Step

**Step 1:** Write deterministic HTML table parser

**Approach:**
1. Fetch pricing HTML directly (not markdown)
2. Use BeautifulSoup to parse table structure
3. Extract row labels and cell values into dict
4. Apply deterministic field extractors (regex on cell text)
5. Validate against PricingExtended schema
6. Compare output to baseline fixtures

**Expected outcome:**
- 41/41 pricing extraction (vs 40/41 baseline)
- $0 Bedrock cost (vs ~$0.07 baseline)
- Deterministic output (vs LLM randomness)
- Unit-testable extractors (vs black-box LLM)

---

**Status:** ✅ COMPLETE

**Ready for:** Path B deterministic parser implementation
