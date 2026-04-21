# WalletSync - Project Structure

## Overview
Complete credit card data extraction and enrichment pipeline using web scraping, data transformation, and AWS Bedrock LLM.

## Directory Structure

```
WalletSync/
├── .env                          # AWS credentials (gitignored)
├── .gitignore                    # Git ignore rules
├── README.md                     # Main documentation
├── requirements.txt              # Python dependencies
├── PROJECT_STRUCTURE.md          # This file
│
├── src/                          # Source code
│   ├── chase_scraper.py          # Playwright web scraper (267 lines)
│   ├── clean_data.py             # Data transformation script (180 lines)
│   └── extract_fees_bedrock.py   # AWS Bedrock fee extraction (260 lines)
│
└── output/                       # Generated data files
    ├── chase_cards.json          # Raw scraped data (82 cards, 85 KB)
    ├── chase_cards_clean.json    # Cleaned & structured data (82 cards, 37 KB)
    ├── extracted_fees.json       # Bedrock-extracted fees (3 cards, 1 KB)
    ├── TRANSFORMATION_SUMMARY.md # Data cleaning documentation
    └── BEDROCK_EXTRACTION_SUMMARY.md  # Bedrock execution report
```

## File Descriptions

### Configuration Files

| File | Purpose |
|------|---------|
| `.env` | AWS credentials (ACCESS_KEY_ID, SECRET_ACCESS_KEY, REGION) |
| `.gitignore` | Excludes sensitive files and temp data from git |
| `requirements.txt` | Python package dependencies |

### Source Scripts

| Script | Purpose | Key Features |
|--------|---------|--------------|
| `chase_scraper.py` | Web scraping | Playwright headless, dynamic content handling, 82 cards |
| `clean_data.py` | Data transformation | Regex parsing, type conversion, 60% size reduction |
| `extract_fees_bedrock.py` | Fee extraction | AWS Bedrock, tool calling, Markdown conversion |

### Output Data

| File | Description | Size | Records |
|------|-------------|------|---------|
| `chase_cards.json` | Raw HTML text from scraping | 85 KB | 82 |
| `chase_cards_clean.json` | Structured, typed data | 37 KB | 82 |
| `extracted_fees.json` | Fee data from pricing terms | 1 KB | 3 |

### Documentation

| File | Content |
|------|---------|
| `README.md` | Setup, usage, and workflow |
| `TRANSFORMATION_SUMMARY.md` | Data cleaning methodology |
| `BEDROCK_EXTRACTION_SUMMARY.md` | Bedrock execution details |
| `PROJECT_STRUCTURE.md` | This file |

## Data Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. WEB SCRAPING (chase_scraper.py)                             │
│    Input:  https://creditcards.chase.com/all-credit-cards      │
│    Output: chase_cards.json (raw HTML text)                    │
│    Tool:   Playwright (headless Chrome)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. DATA TRANSFORMATION (clean_data.py)                         │
│    Input:  chase_cards.json                                    │
│    Output: chase_cards_clean.json (structured JSON)            │
│    Tool:   Regex parsing, type conversion                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. FEE EXTRACTION (extract_fees_bedrock.py)                    │
│    Input:  chase_cards_clean.json → pricing_terms_url          │
│    Output: extracted_fees.json (fee data)                      │
│    Tool:   AWS Bedrock (Claude 3 Haiku)                        │
└─────────────────────────────────────────────────────────────────┘
```

## Data Schema Evolution

### Stage 1: Raw Scraped Data
```json
{
  "card_name": "Chase Freedom Unlimited®\nLinks to product page",
  "annual_fee": "ANNUAL FEE\n\n$0†",
  "offer_threshold": "Earn a $250 bonus after you spend $500..."
}
```

### Stage 2: Cleaned Data
```json
{
  "card_name": "Chase Freedom Unlimited®",
  "annual_fee_usd": 0,
  "sign_up_bonus_value": 250,
  "sign_up_bonus_spend_req": 500
}
```

### Stage 3: Enriched with Fees
```json
{
  "card_name": "Chase Freedom Unlimited®",
  "annual_fee_usd": 0,
  "foreign_transaction_fee_percentage": 3.0,
  "balance_transfer_fee_description": "Either $5 or 5%...",
  "late_penalty_fee_usd": 40,
  "cash_advance_apr": 28.49
}
```

## Dependencies

```
playwright>=1.44.0      # Web scraping
boto3>=1.34.0          # AWS SDK
markdownify>=0.11.6    # HTML to Markdown
python-dotenv>=1.0.0   # Environment variables
```

## Key Metrics

| Metric | Value |
|--------|-------|
| Total cards scraped | 82 |
| Cards with pricing URLs | 41 |
| Cards processed by Bedrock | 3 (test batch) |
| Data size reduction | 60% (85 KB → 37 KB) |
| Bedrock cost per card | ~$0.0007 |
| Total execution time | ~2 minutes (all stages) |

## Usage

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Configure AWS credentials in .env
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_DEFAULT_REGION=us-east-1

# 3. Run pipeline
python src/chase_scraper.py        # Scrape cards
python src/clean_data.py           # Transform data
python src/extract_fees_bedrock.py # Extract fees (requires AWS)
```

## Next Steps

1. **Scale Bedrock extraction** - Process all 41 cards with pricing URLs
2. **Merge datasets** - Combine fee data with main card dataset
3. **Add more fields** - Extract additional fees and terms
4. **Automate updates** - Schedule periodic re-scraping
5. **Build API** - Serve data via REST API
6. **Create dashboard** - Visualize card comparisons
