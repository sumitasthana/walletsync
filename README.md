# WalletSync - Credit Card Data Extractor

Extract comprehensive credit card data from Chase including pricing terms and rewards programs.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set AWS credentials (for Bedrock API)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# List available cards
python extract_card_data.py --list

# Extract a single card
python extract_card_data.py --card-id freedom-flex-a6950e

# Extract first 5 cards
python extract_card_data.py --batch 5
```

## Features

✅ **41 Chase credit cards** - Complete coverage  
✅ **27 pricing fields** - APRs, fees, intro periods  
✅ **Deterministic pricing extraction** - 100% success rate, zero hallucinations, $0 cost  
✅ **Nested rewards data** - Earning categories, redemption options, transfer partners  
✅ **Pydantic validation** - Type-safe schemas with business rules  
✅ **Idempotent & resumable** - Skips already processed cards  
✅ **Cost efficient** - ~$0.001 per card (rewards only, pricing is free)  

## Output Files

### Individual Card Files
`data/cards/<card_id>.json` - Complete merged data per card

```json
{
  "_meta": {...},
  "card_info": {
    "card_name": "Chase Freedom Flex®",
    "annual_fee_usd": 0,
    "sign_up_bonus_value": 200,
    ...
  },
  "pricing": {
    "purchase_apr_min": 18.24,
    "foreign_transaction_fee_pct": 3.0,
    ...
  },
  "rewards": {
    "earning_categories": [...],
    "redemption_options": [...],
    "transfer_partners": [...]
  }
}
```

### Combined Files
- `data/extracted_pricing_extended.json` - All pricing data
- `data/extracted_rewards_extended.json` - All rewards data

## Documentation

See [USAGE.md](docs/USAGE.md) for complete documentation including:
- Command line options
- Data schemas
- Pipeline stages
- Cost estimates
- Troubleshooting

## Project Structure

```
WalletSync/
├── extract_card_data.py                    # Main CLI application
├── requirements.txt
├── docs/                                   # Guides and run reports
│   ├── USAGE.md                            # Complete usage guide
│   ├── DATA_QUALITY_TIERS.md               # Data quality tier contract
│   ├── PATH_B_COMPLETE.md                 # Deterministic pricing notes
│   └── reports/                           # Run summaries and investigations
├── scripts/                               # One-off utilities
│   ├── capture_html_fixtures.py
│   ├── check_coverage.py
│   ├── create_pricing_fixtures.py
│   ├── investigate_rewards_urls.py
│   └── verify_coverage.py
├── src/
│   ├── common/
│   │   ├── schemas.py                      # Pydantic models
│   │   ├── dump_utils.py
│   │   └── pdf_utils.py
│   ├── pricing/
│   │   ├── dump_pricing_text.py            # HTML to structured JSON
│   │   ├── parse_pricing_deterministic.py  # Deterministic parser (Path B)
│   │   └── extract_pricing_extended_LEGACY.py  # DEPRECATED, kept for reference
│   ├── rewards/
│   │   ├── dump_rewards_text.py            # PDF to text
│   │   ├── extract_rewards_extended.py     # LLM rewards parser (PDF)
│   │   └── extract_rewards_html_fallback.py # LLM rewards parser (HTML)
│   └── scraper/
│       ├── chase_scraper.py                # Initial scraper
│       └── clean_data.py                   # Data cleaning
├── tests/
│   ├── test_pricing_parser.py              # Unit tests for deterministic parser
│   ├── test_pricing_regression.py          # Regression tests vs LLM baseline
│   └── fixtures/                           # HTML fixtures for testing
└── data/
    ├── chase_cards.json                    # Raw scraped data
    ├── chase_cards_clean.json              # Cleaned base card data
    ├── extracted_pricing_extended.json     # All pricing (deterministic)
    ├── extracted_rewards_extended.json     # PDF rewards (LLM)
    ├── extracted_rewards_html_fallback.json # HTML rewards (LLM)
    ├── cards/                              # Merged per-card JSONs
    └── raw/                               # Structured JSON and text dumps
```

## Extraction Architecture

**Pricing (Deterministic - Path B):**
- HTML tables → BeautifulSoup → Regex extractors → PricingExtended
- 100% success rate, $0 cost, <1 second
- See `docs/PATH_B_COMPLETE.md` for details

**Rewards (LLM):**
- PDF/HTML → LLM (Bedrock Claude 3 Haiku) → RewardsExtended
- ~60% coverage, ~$0.05 per run, ~3 minutes
- Appropriate for unstructured reward program descriptions
```

## License

MIT
