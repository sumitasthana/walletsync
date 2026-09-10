# Chase Data Folder - File Purposes

## File Categories

### 📥 INPUT FILES (Pre-existing, used by extraction pipeline)

**`cards.json`** (85 KB)
- **Purpose**: Raw scraped data from Chase website
- **Created by**: `python src/banks/chase/scraper.py`
- **Contains**: 82 raw card records with all scraped fields
- **Used by**: `clean_data.py` as input
- **Status**: ✅ Keep - Required for pipeline

**`cards_clean.json`** (24 KB)
- **Purpose**: Cleaned and deduplicated base card data
- **Created by**: `python src/scraper/clean_data.py --bank chase`
- **Contains**: 41 unique cards with standardized fields + card_id
- **Used by**: All extraction scripts as the master card list
- **Status**: ✅ Keep - Required for pipeline

---

### 🔄 INTERMEDIATE FILES (Reusable dumps, cached for efficiency)

**`raw/pricing/*.json`** (41 files)
- **Purpose**: HTML pricing pages converted to structured JSON
- **Created by**: `dump_pricing_text.py`
- **Contains**: Schumer Box rows and full page text per card
- **Used by**: `parse_pricing_deterministic.py` as input
- **Reusable**: Yes - skipped if <24 hours old (unless --force)
- **Status**: ⚠️ Optional - Can regenerate, but saves time/bandwidth

**`raw/rewards/*.txt`** (13 files)
- **Purpose**: PDF rewards agreements converted to plain text
- **Created by**: `dump_rewards_text.py`
- **Contains**: Full text extracted from PDF files
- **Used by**: `extract_rewards_extended.py` as input
- **Reusable**: Yes - skipped if <24 hours old (unless --force)
- **Status**: ⚠️ Optional - Can regenerate, but saves time/bandwidth

---

### 📤 OUTPUT FILES (Final extracted data)

**`extracted_pricing_extended.json`** (3 KB)
- **Purpose**: Combined pricing data for all processed cards
- **Created by**: `parse_pricing_deterministic.py`
- **Contains**: Array of pricing records (27 fields per card)
- **Format**:
  ```json
  [
    {"_meta": {...}},
    {"card_id": "...", "purchase_apr_min": 18.24, ...},
    ...
  ]
  ```
- **Status**: ✅ Keep - Primary output

**`extracted_rewards_extended.json`** (5 KB)
- **Purpose**: Combined rewards data for all processed cards
- **Created by**: `extract_rewards_extended.py`
- **Contains**: Array of rewards records with nested structures
- **Format**:
  ```json
  [
    {"_meta": {...}},
    {"card_id": "...", "earning_categories": [...], ...},
    ...
  ]
  ```
- **Status**: ✅ Keep - Primary output

**`cards/<card_id>.json`** (1 file shown, 4 KB)
- **Purpose**: Complete merged data for individual cards
- **Created by**: `extract_card_data.py` (main CLI)
- **Contains**: card_info + pricing + rewards merged into one file
- **Format**:
  ```json
  {
    "_meta": {...},
    "card_info": {...},
    "pricing": {...},
    "rewards": {...}
  }
  ```
- **Status**: ✅ Keep - Final output (one file per card)

---

## Pipeline Flow

```
INPUT FILES
├── cards.json (raw scraped)
└── cards_clean.json (cleaned)
         ↓
INTERMEDIATE FILES (dumps)
├── raw/pricing/*.md (HTML → Markdown)
└── raw/rewards/*.txt (PDF → Text)
         ↓
OUTPUT FILES (extracted)
├── extracted_pricing_extended.json (all pricing)
├── extracted_rewards_extended.json (all rewards)
└── cards/*.json (merged per card)
```

---

## What Gets Produced When You Run Commands

### `python extract_card_data.py --card-id freedom-flex-a6950e`

**Produces:**
1. `raw/pricing/freedom-flex-a6950e.json` (if doesn't exist)
2. `raw/rewards/freedom-flex-a6950e.txt` (if doesn't exist)
3. Updates `extracted_pricing_extended.json` (adds/updates record)
4. Updates `extracted_rewards_extended.json` (adds/updates record)
5. Creates `cards/freedom-flex-a6950e.json` (merged output)

### `python extract_card_data.py --batch 5`

**Produces:**
1. 5 files in `raw/pricing/`
2. 5 files in `raw/rewards/`
3. Updates `extracted_pricing_extended.json` (5 records)
4. Updates `extracted_rewards_extended.json` (5 records)
5. Creates 5 files in `cards/`

---

## Which Files Should You Keep?

### ✅ MUST KEEP (Essential)
- `cards_clean.json` - Master card list
- `extracted_pricing_extended.json` - Final pricing database
- `extracted_rewards_extended.json` - Final rewards database
- `cards/*.json` - Individual card outputs

### ⚠️ OPTIONAL (Can regenerate)
- `cards.json` - Can re-scrape from Chase
- `raw/pricing/*.md` - Can re-dump from URLs
- `raw/rewards/*.txt` - Can re-download PDFs

### ❌ CAN DELETE (If space is tight)
- `raw/` folder entirely - Will regenerate on next run
- `cards.json` - Only needed if you want to re-clean

---

## Recommended Cleanup

If you want to minimize storage:

```bash
# Keep only final outputs
rm -rf data/chase/raw/
rm data/chase/cards.json

# Keep these:
# - data/chase/cards_clean.json
# - data/chase/extracted_pricing_extended.json
# - data/chase/extracted_rewards_extended.json
# - data/chase/cards/*.json
```

The pipeline will regenerate `raw/` dumps as needed on the next run.

---

## File Size Summary

| Category | Files | Total Size | Keep? |
|----------|-------|------------|-------|
| Input | 2 | 109 KB | ✅ Yes |
| Intermediate (dumps) | 6 | 76 KB | ⚠️ Optional |
| Output (final) | 3+ | ~12 KB + (4KB × cards) | ✅ Yes |

**Total current size**: ~190 KB for 3 processed cards
