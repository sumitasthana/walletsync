# WalletSync - Credit Card Data Extractor

Extract comprehensive credit card data from supported banks including pricing terms and rewards programs. Chase is fully supported; PNC is under investigation (see `docs/reports/pnc_spike.md`).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set AWS credentials (for Bedrock API)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# List supported banks
python extract_card_data.py --list-banks

# List available cards for a bank (default: chase)
python extract_card_data.py --bank chase --list

# Extract a single card
python extract_card_data.py --card-id freedom-flex-a6950e

# Extract first 5 cards
python extract_card_data.py --bank chase --batch 5
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
`data/chase/cards/<card_id>.json` - Complete merged data per card

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
- `data/chase/extracted_pricing_extended.json` - All pricing data
- `data/chase/extracted_rewards_extended.json` - All rewards data

## Documentation

See [USAGE.md](docs/USAGE.md) for complete documentation including:
- Command line options
- Data schemas
- Pipeline stages
- Cost estimates
- Troubleshooting

## Supported Banks

| Bank | Status | Cards |
|------|--------|-------|
| chase | ready | 41 |
| pnc | spike (investigation only) | - |

Each bank keeps its data under `data/<bank>/`. To add another issuer, see
[ONBOARDING_NEW_BANK.md](docs/ONBOARDING_NEW_BANK.md).

## Project Structure

```
WalletSync/
├── extract_card_data.py                    # Main CLI application
├── requirements.txt
├── docs/                                   # Guides and run reports
│   ├── USAGE.md                            # Complete usage guide
│   ├── DATA_QUALITY_TIERS.md               # Data quality tier contract
│   ├── ONBOARDING_NEW_BANK.md              # New bank onboarding runbook
│   ├── PATH_B_COMPLETE.md                 # Deterministic pricing notes
│   └── reports/                           # Run summaries and investigations
├── scripts/                               # One-off utilities
│   ├── capture_html_fixtures.py
│   ├── check_coverage.py
│   ├── create_pricing_fixtures.py
│   ├── investigate_rewards_urls.py
│   └── verify_coverage.py
├── src/
│   ├── banks/
│   │   ├── base.py                        # BankConfig and path helpers
│   │   ├── chase/                         # Chase adapter (scraper.py)
│   │   └── pnc/                           # PNC adapter (spike only)
│   ├── common/
│   │   ├── schemas.py                      # Pydantic models
│   │   ├── merge.py                       # Per-card merge logic
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
│       └── clean_data.py                   # Data cleaning (bank-aware)
├── tests/
│   ├── test_banks.py                       # Bank registry tests
│   ├── test_pricing_parser.py              # Unit tests for deterministic parser
│   ├── test_pricing_regression.py          # Regression tests vs LLM baseline
│   └── fixtures/                           # HTML fixtures for testing
└── data/
    ├── README.md                           # Data layout guide
    ├── chase/                              # Chase: cards.json, cards_clean.json,
    │                                       #   raw/, extracted_*.json, cards/
    ├── pnc/                                # PNC spike captures
    └── unified/                            # Cross-bank combined dataset
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

## License

MIT
