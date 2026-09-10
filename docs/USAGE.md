# WalletSync Card Data Extractor - Usage Guide

## Overview

The WalletSync Card Data Extractor is a CLI application that extracts comprehensive credit card data from supported bank card pages (default: Chase), including pricing terms and rewards program details.

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up AWS credentials (for Bedrock API)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

## Quick Start

### List Supported Banks

```bash
python extract_card_data.py --list-banks
```

### List Available Cards

```bash
# Default bank is chase
python extract_card_data.py --list

# Or explicitly
python extract_card_data.py --bank chase --list
```

This shows all 41 Chase cards with their card IDs and available data sources (pricing/rewards).

### Extract Single Card

```bash
# Extract by card ID (fastest - uses existing dumps)
python extract_card_data.py --card-id freedom-flex-a6950e --skip-dumps

# Extract with fresh dumps
python extract_card_data.py --card-id freedom-flex-a6950e
```

### Extract Multiple Cards

```bash
# Extract first 5 cards
python extract_card_data.py --batch 5

# Force re-extraction
python extract_card_data.py --batch 5 --force
```

## Output Files

The application generates three types of output:

### 1. Individual Card Files
**Location**: `data/chase/cards/<card_id>.json`

Each file contains complete card data with three sections:

```json
{
  "_meta": {
    "card_id": "freedom-flex-a6950e",
    "extracted_at": "2026-04-21T16:17:39Z",
    "data_sources": ["pricing_extended", "rewards_extended"]
  },
  "card_info": {
    "card_id": "freedom-flex-a6950e",
    "card_name": "Chase Freedom Flex®",
    "annual_fee_usd": 0,
    "reward_currency": "Cash Back",
    "sign_up_bonus_value": 200,
    ...
  },
  "pricing": {
    "purchase_apr_min": 18.24,
    "purchase_apr_max": 27.74,
    "foreign_transaction_fee_pct": 3.0,
    "late_payment_fee_max_usd": 40,
    ...
  },
  "rewards": {
    "earning_categories": [
      {
        "category": "dining",
        "rate": 3.0
      },
      ...
    ],
    "redemption_options": [...],
    "transfer_partners": [...]
  }
}
```

### 2. Combined Pricing Data
**Location**: `data/chase/extracted_pricing_extended.json`

Array of all extracted pricing data with 27 fields per card including:
- APR ranges (purchase, balance transfer, cash advance, penalty)
- Intro APR periods
- All fees (foreign transaction, balance transfer, cash advance, late payment, authorized user)
- APR index and margins

### 3. Combined Rewards Data
**Location**: `data/chase/extracted_rewards_extended.json`

Array of all extracted rewards data with nested structures:
- Earning categories (with caps, activation requirements)
- Redemption options (with value per point)
- Transfer partners (with ratios)
- Points expiration
- Bonus disqualifying products

## Command Line Options

```
usage: extract_card_data.py [-h] (--url URL | --card-id CARD_ID | --batch N | --list | --list-banks)
                            [--bank BANK] [--force] [--skip-dumps]
                            [--output-dir OUTPUT_DIR]

Extract comprehensive credit card data from supported banks

optional arguments:
  -h, --help            show this help message and exit
  --url URL             Card URL to extract (not yet implemented)
  --card-id CARD_ID     Card ID from cleaned data
  --batch N             Extract first N cards
  --list                List available cards
  --list-banks          List supported banks
  --bank BANK           Bank key (default: chase; see --list-banks)
  --force               Force re-extraction even if data exists
  --skip-dumps          Skip dump step (use existing dumps)
  --output-dir OUTPUT_DIR
                        Output directory for individual card JSONs (default: data/<bank>/cards)
```

## Pipeline Stages

The extraction pipeline has 3 stages:

### Stage 1: Raw Dumps
- Scrapes pricing pages (HTML → structured JSON)
- Downloads rewards PDFs (PDF → Text)
- Saves to `data/chase/raw/pricing/` and `data/chase/raw/rewards/`
- **Skip with**: `--skip-dumps` (uses existing dumps)

### Stage 2: Structured Extraction
- Pricing is parsed deterministically (no LLM, no cost)
- Rewards are extracted with AWS Bedrock (Claude 3 Haiku)
- Validates with Pydantic schemas
- Saves to `data/chase/extracted_pricing_extended.json` and `data/chase/extracted_rewards_extended.json`

### Stage 3: Merge & Save
- Merges pricing + rewards + base card data
- Saves individual card files to `data/chase/cards/`

## Examples

### Extract a specific card with fresh data
```bash
python extract_card_data.py --card-id sapphire-reserve-4f5bd8
```

### Extract first 10 cards (skip dumps if they exist)
```bash
python extract_card_data.py --batch 10 --skip-dumps
```

### Force complete re-extraction of 3 cards
```bash
python extract_card_data.py --batch 3 --force
```

### List all available cards
```bash
python extract_card_data.py --list
```

## Data Schema

### Pricing Fields (27 total)
- **APRs**: purchase_apr_min/max, bt_apr_min/max, cash_advance_apr, penalty_apr_max
- **Intro APRs**: purchase_apr_intro_pct/months, bt_apr_intro_pct/months/window_days
- **Fees**: foreign_transaction_fee_pct, balance_transfer_fee (pct/min/max), cash_advance_fee (pct/min), late_payment_fee_max_usd, authorized_user_fee_usd
- **Index**: apr_index, purchase_apr_margin, apr_disclosure_date

### Rewards Fields
- **Core**: reward_currency, point_value_cents_baseline
- **Earning**: earning_categories[] (category, rate, cap_usd, cap_period, requires_activation, notes)
- **Redemption**: redemption_minimum_usd, redemption_options[] (method, value_cents_per_point, notes)
- **Transfers**: transfer_partners[] (partner_name, ratio_from, ratio_to, notes)
- **Constraints**: points_expiration_months, bonus_disqualifying_products[]
- **Benefits**: cardmember_anniversary_benefit

## Cost Estimates

- **Per card**: ~$0.015-0.02 (using Claude 3 Haiku)
- **Batch of 10**: ~$0.15-0.20
- **All 41 cards**: ~$0.60-0.80

## Troubleshooting

### "Card ID not found"
- Run `--list` to see available card IDs
- Card IDs are in format: `category-name-hash` (e.g., `freedom-flex-a6950e`)

### "Pricing extraction failed"
- Check AWS credentials are set
- Verify dumps exist in `data/chase/raw/pricing/`
- Try with `--force` to regenerate dumps

### "No cards with URLs found"
- Some cards may not have pricing_terms_url or rewards_agreement_url
- Use `--list` to see which cards have data sources

## Advanced Usage

### Extract only pricing data
```bash
python src/pricing/parse_pricing_deterministic.py --bank chase
```

### Extract only rewards data
```bash
python src/rewards/extract_rewards_extended.py --bank chase
```

### Generate dumps only
```bash
python src/pricing/dump_pricing_text.py --bank chase
python src/rewards/dump_rewards_text.py --bank chase
```

## Document Chat

`src/agent/toc_chat.py` is a LangGraph agent that answers questions about
card terms from the captured documents, with citations. The agent graph is
built in `src/agent/graph.py` (`langchain.agents.create_agent` on
`ChatBedrockConverse`); its tools live in `src/agent/tools.py`.

Single-card mode puts that card's documents straight into the model context,
so it needs no index:

```bash
python src/agent/toc_chat.py --card-id freedom-flex-a6950e
```

Retrieval mode answers questions across many cards using a local vector
index (ChromaDB at `data/vector_index/`, embeddings via Amazon Titan).
Build the index first, then chat:

```bash
python src/rag/build_index.py            # all banks with data
python src/agent/toc_chat.py --bank chase
python src/agent/toc_chat.py             # everything indexed
```

The agent has four tools: `search_documents` (vector search over Schumer
Box rows, full pricing text, rewards agreements, and marketing copy),
`get_card` (the structured pricing and rewards record for one card),
`get_pricing_field` (one field for all cards, for which-cards questions),
and `list_cards` (card ids and names only). Tool calls are printed as they
run. Each question costs a fraction of a cent on Claude 3 Haiku.

Re-run `src/rag/build_index.py` after new dumps are captured. Unchanged
chunks are skipped, so only new text is embedded.

## File Structure

```
WalletSync/
├── extract_card_data.py          # Main CLI application
├── docs/                         # Guides and run reports
├── scripts/                     # One-off utilities
├── src/
│   ├── banks/                   # Bank registry, Chase and PNC adapters
│   ├── common/                   # schemas, merge, dump_utils, pdf_utils
│   ├── pricing/                  # dump, deterministic parser, legacy LLM
│   ├── rewards/                  # dump, PDF parser, HTML fallback
│   └── scraper/                 # clean_data (bank-aware)
├── tests/
│   ├── test_banks.py
│   ├── test_pricing_parser.py
│   ├── test_pricing_regression.py
│   └── fixtures/
└── data/
    ├── chase/                    # Per-bank data for Chase
    │   ├── cards.json            # Raw scraped data
    │   ├── cards_clean.json    # Cleaned base card data
    │   ├── extracted_pricing_extended.json
    │   ├── extracted_rewards_extended.json
    │   ├── extracted_rewards_html_fallback.json
    │   ├── cards/                # Merged per-card JSON files
    │   └── raw/
    │       ├── pricing/          # Structured JSON dumps
    │       └── rewards/          # PDF text dumps
    ├── pnc/                      # PNC spike captures
    └── unified/                  # Cross-bank combined dataset
```
