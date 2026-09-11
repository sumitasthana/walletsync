# WalletSync

Every detail of your credit cards, including the ones buried in the lengthy
terms and conditions nobody reads, mapped to how you actually spend.

WalletSync optimizes your credit card usage. It gathers the full detail of
each card, reads the fine print in pricing terms and rewards agreements, and
maps it against your spending so you always know which card should be
top-of-the-wallet: the one to reach for first, and the one to use for each
kind of purchase.

## The problem

Card issuers publish the full truth about their products in dense documents:
a pricing terms sheet with every APR, fee, and intro period, and a rewards
agreement with earning categories, caps, activation rules, redemption values,
and transfer partners. The marketing page shows the sign-up bonus and skips
the rest. The 4% category that stops after $8,000 a year, the quarterly
categories you forgot to activate, the points that expire, the 3% foreign
transaction fee: almost nobody reads those documents, so almost nobody uses
their cards optimally.

## What WalletSync does

1. Gathers the card lineup and documents for each supported bank (Chase
   today, PNC next, more via the onboarding runbook)
2. Reads the fine print: a deterministic parser extracts the full pricing
   table (the Schumer Box) with 100% accuracy and zero cost, and LLM
   extraction pulls the rewards structure out of agreement documents
3. Validates every record against strict schemas with business rules, so a
   made-up fee or category fails loudly instead of silently reaching your
   recommendations
4. Merges all banks into one unified dataset, with a data quality tier on
   every card
5. Maps the data to your usage and suggests your top-of-the-wallet card:
   which card to pay with at restaurants, which one for subscriptions, and
   which single card should be your default
6. Explains the fine print on demand: an agent chats over the actual
   documents and answers in plain language, with citations

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

## Ask the fine print

Chat with the actual documents. The agent reads the pricing terms and
rewards agreements and answers in plain language, with citations:

```bash
# One card, documents straight into context (no index needed)
python src/agent/toc_chat.py --card-id freedom-flex-a6950e

# Across a bank or the whole wallet (requires the index)
python src/rag/build_index.py
python src/agent/toc_chat.py --bank chase
```

Try: "what happens if I pay late?", "when do my points expire?",
"which cards have no foreign transaction fee?"

## Match cards to how you spend

A React and TypeScript workspace with interactive card responses in a single
conversation. As you type your needs, a shortlist previews in the main window.
Send your message to keep its cards and comparison with that answer. Additional
explanations are available in an expandable section below the results.
Card details show reward rates, fees, caps, and activation requirements.

```bash
npm --prefix frontend ci
npm --prefix frontend run build
python src/web/app.py
# Open http://127.0.0.1:5000
```

The frontend requires Node.js 22.12+ or 24+. Flask serves the Vite production
build from `src/web/static/app`. Rebuild after changing the frontend.
For hot reload, keep Flask running and use `npm --prefix frontend run dev`;
open the URL Vite prints. Its development server proxies API and card image
requests to Flask on port 5000.

Live matching uses local card data and works without AWS. Assistant replies
require AWS credentials with Bedrock access. Document search also requires
the local vector index. Failures show a retry option while keeping live
matches available. Conversations stay in tab memory and clear on refresh or
New chat; messages are sent to the backend and Bedrock for replies.

See [frontend setup and tests](frontend/README.md) for development commands.

## The buried details it captures

- Purchase, balance transfer, cash advance, and penalty APRs, including
  ranges, margins over the Prime Rate, and intro periods with month counts
- Foreign transaction, balance transfer, cash advance, late payment, and
  authorized user fees, including minimums and maximums
- Earning categories with their fine print: annual combined caps, quarterly
  activation requirements, merchant category exclusions
- Redemption values for every method (cash back, statement credit, travel
  portal, transfer partners) and minimum redemption amounts
- Transfer partner ratios, point expiration rules, and the products that
  disqualify a sign-up bonus

## Where it stands

| Capability | Status |
|---|---|
| Chase card lineup | Done: 41 cards scraped and cleaned |
| Pricing extraction (deterministic) | Done: 41/41 cards, 100% accuracy against reviewed source data, $0 cost |
| Rewards extraction (PDF and HTML tiers) | Done: 26/41 cards in tier 1 or tier 2 |
| Multi-bank architecture and unified dataset | Done |
| Document chat with citations | Done: LangGraph agent over the raw terms corpus, 1595 chunks in a local vector index |
| Card images | Done: 41 Chase images fetched and normalized to 640x400 PNG; PNC via manual capture |
| Live card-matching UI | Done: deterministic matcher ranks cards as you type; LangGraph agent explains picks |
| PNC onboarding | Spike complete, pipeline is the next effort |
| Usage profile and top-of-wallet suggestions | Roadmap: the next milestone, built on the unified dataset |

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
| pnc | manifest onboarded, document capture pending | 4 |

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
