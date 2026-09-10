# Data Layout

All pipeline data is namespaced per bank under `data/<bank>/`:

```
data/
├── chase/    Chase cards (see chase/README.md for file purposes)
├── pnc/      PNC cards (spike only, see docs/reports/pnc_spike.md)
└── unified/  Cross-bank combined dataset (all_cards.json)
```

Each bank folder holds the same layout:

- `cards.json` - raw scraped card list
- `cards_clean.json` - cleaned and deduplicated base card data
- `raw/pricing/` - structured pricing page dumps (per card)
- `raw/rewards/` - rewards agreement PDF text dumps (per card)
- `extracted_pricing_extended.json` - structured pricing output
- `extracted_rewards_extended.json` - structured rewards output (PDF tier)
- `extracted_rewards_html_fallback.json` - structured rewards output (HTML tier)
- `cards/` - merged per-card files (pricing + rewards)
- `images/` - card art per card (`<card_id>.png`, 640x400 PNG), with
  source URLs in `images/manifest.json`

The unified dataset is rebuilt with:

```
python extract_card_data.py --build-unified
```

To add a new bank, see `docs/ONBOARDING_NEW_BANK.md`.
