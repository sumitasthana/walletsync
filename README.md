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
`output/cards/<card_id>.json` - Complete merged data per card

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
- `output/extracted_pricing_extended.json` - All pricing data
- `output/extracted_rewards_extended.json` - All rewards data

## Documentation

See [USAGE.md](USAGE.md) for complete documentation including:
- Command line options
- Data schemas
- Pipeline stages
- Cost estimates
- Troubleshooting

## Project Structure

```
WalletSync/
├── extract_card_data.py                    # Main CLI application
├── src/
│   ├── chase_scraper.py                    # Initial scraper
│   ├── clean_data.py                       # Data cleaning
│   ├── dump_pricing_text.py                # HTML → Structured JSON
│   ├── dump_rewards_text.py                # PDF → Text
│   ├── parse_pricing_deterministic.py      # Deterministic pricing parser (Path B)
│   ├── extract_pricing_extended_LEGACY.py  # DEPRECATED - LLM-based (kept for reference)
│   ├── extract_rewards_extended.py         # LLM rewards parser (PDF)
│   ├── extract_rewards_html_fallback.py    # LLM rewards parser (HTML)
│   ├── build_unified_dataset.py            # Merge pricing + rewards
│   ├── schemas.py                          # Pydantic models
│   ├── dump_utils.py
│   └── pdf_utils.py
├── tests/
│   ├── test_pricing_parser.py              # 39 unit tests for deterministic parser
│   ├── test_pricing_regression.py          # Regression tests vs LLM baseline
│   └── fixtures/                           # HTML fixtures for testing
└── output/
    ├── extracted_pricing_extended.json     # All pricing (deterministic)
    ├── extracted_rewards_extended.json     # PDF rewards (LLM)
    ├── extracted_rewards_html_fallback.json # HTML rewards (LLM)
    ├── unified_card_data.json              # Combined dataset
    └── raw/                                # Structured JSON & text dumps
```

## Extraction Architecture

**Pricing (Deterministic - Path B):**
- HTML tables → BeautifulSoup → Regex extractors → PricingExtended
- 100% success rate, $0 cost, <1 second
- See `PATH_B_COMPLETE.md` for details

**Rewards (LLM):**
- PDF/HTML → LLM (Bedrock Claude 3 Haiku) → RewardsExtended
- ~60% coverage, ~$0.05 per run, ~3 minutes
- Appropriate for unstructured reward program descriptions
```

## License

MIT
