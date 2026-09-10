# Onboarding a New Bank

This is the standing runbook for adding a card issuer to WalletSync. It was
written after the Chase migration and the PNC spike, so both are referenced
as worked examples. Expect the whole process to be mostly investigation and
one adapter; the shared pipeline (cleaning, parsing, extraction, merging,
unified dataset) should not need changes for a typical US issuer.

## Principles

- Data for a bank never mixes with another bank's: everything lives under
  `data/<bank>/` with the same internal layout.
- A bank is a small config plus (if needed) a scraper and label variants.
  There is deliberately no plugin framework. With two banks, a dataclass and
  a dict registry are enough; revisit the abstraction at bank three.
- Investigation comes before code. Do not write a parser for a document you
  have not looked at.
- Raw dumps are the working state. Once pages or PDFs are dumped, every later
  stage runs offline and can be re-run cheaply.

## Step 1: Spike the bank's site

Answer these questions before writing any code (see
`docs/reports/pnc_spike.md` for the PNC example):

1. Where is the card listing page? How many cards?
2. What does a product page look like? Is there a clean URL pattern for
   card IDs?
3. What format are the pricing terms: HTML with Schumer Box tables, or PDF?
4. What format are the rewards terms: PDF agreement, HTML page, both?
5. Does the site block automated access (headless browser, plain requests)?
6. Do the marketing blurbs follow the same shapes as existing banks
   ("$0 Annual Fee", "Earn a $X bonus after $Y in purchases in Z months",
   "N% on all other purchases")?

Write the findings to `docs/reports/<bank>_spike.md` and record the decision
on pricing extraction (deterministic vs LLM) with the evidence.

## Step 2: Register the bank

1. Create `src/banks/<key>/__init__.py` with a BankConfig:

```python
from src.banks.base import BankConfig

<KEY> = BankConfig(
    key="<key>",                 # directory and CLI name
    display_name="<Name>",
    status="spike",              # flip to "ready" when the pipeline works
    category_extensions=(),      # earning categories beyond BASE_CATEGORIES
)
```

2. Register it in `src/banks/__init__.py` (BANKS dict).
3. Run `python extract_card_data.py --list-banks` to confirm it appears.
4. Add `data/<key>/` (created on demand; `data/<key>/*.json` outputs are
   gitignored except tracked inputs you choose to commit).

## Step 3: Produce `data/<key>/cards.json`

The raw card list must use the standard 10-field schema so the shared
cleaning stage works unchanged:

```
card_name, details_url, annual_fee, apr_info, marketing_tag,
offer_headline, offer_threshold, earning_rates,
pricing_terms_url, rewards_agreement_url
```

Two ways to produce it:

- **Scraper** (like `src/banks/chase/scraper.py`): Playwright script in the
  bank package writing to `<bank>.cards_raw_path`. Only do this if the spike
  showed automated access works.
- **Manifest** (PNC's starting path): hand-write the JSON for a small
  lineup. A 4-6 card bank is faster to maintain by hand than to fight bot
  protection. Manual page saves and PDF downloads go into
  `data/<key>/spike/` or directly into `data/<key>/raw/`.

## Step 4: Clean

```
python src/scraper/clean_data.py --bank <key>
```

This writes `data/<key>/cards_clean.json` with `card_id` (slug plus hash of
the product URL, unique across banks) and a `bank` field. Check the output
and adjust heuristics in `clean_data.py` if the bank's marketing copy uses
different phrasing: `generate_card_id` path conventions,
`extract_base_earn_rate` partner keywords, `extract_sign_up_bonus` shapes.

## Step 5: Dump pricing and rewards

- HTML pricing pages: extend `src/pricing/dump_pricing_text.py` only if the
  fetch or validation needs bank-specific handling; it already takes
  `--bank`.
- PDF documents: `src/rewards/dump_rewards_text.py` downloads and extracts
  text via `src/common/pdf_utils.py`. If pricing terms are PDFs too (PNC
  case), add a rates dump that stores text under
  `data/<key>/raw/pricing/`.

Dumps skip existing files unless `--force`, so re-runs are cheap.

## Step 6: Pricing extraction

- HTML Schumer boxes: `src/pricing/parse_pricing_deterministic.py` already
  handles standard label variants. If the new bank uses unseen labels (for
  example a different phrasing for penalty APR), add the label patterns and
  a test fixture first, then re-run.
- PDF Schumer boxes: build a PDF text row extractor that feeds the same
  value parsers. Gate this on validating real PDFs first (see the PNC
  report's recommendation). Fall back to the Bedrock LLM path only if the
  PDF text layout proves unparseable.

## Step 7: Rewards extraction

The existing paths apply unchanged:

- tier_1_pdf: `src/rewards/extract_rewards_extended.py` (Bedrock)
- tier_2_html: `src/rewards/extract_rewards_html_fallback.py`

If the bank needs earning categories outside `BASE_CATEGORIES`, add them to
the bank's `category_extensions` (they join `ALLOWED_CATEGORIES` through the
schema union). Keep the vocabulary strict: unknown categories fail
validation, which is what catches LLM drift.

## Step 8: Run, verify, unify

```
python extract_card_data.py --bank <key> --list
python extract_card_data.py --bank <key> --card-id <some_id> --skip-dumps
python extract_card_data.py --build-unified
```

Verification checklist:

- [ ] New unit tests for any new label patterns or category extensions
- [ ] Full suite passes: `python -m pytest tests\`
- [ ] `--build-unified` includes the new bank with correct tier split
- [ ] `scripts/check_coverage.py` reflects the new bank's coverage
- [ ] Flip `status` to `"ready"` in the bank config
- [ ] Update the Supported Banks table in `README.md`

## Operating model

- **Site changes**: when an issuer redesigns a page, only that bank's
  scraper or label variants break. The shared pipeline and other banks are
  unaffected, and raw dumps let you re-parse old captures without
  re-scraping.
- **Regressions**: per-bank fixtures and the regression tests catch parser
  drift. LLM extraction drift is caught by Pydantic validation.
- **Unified dataset**: rebuild any time with `--build-unified`; it reads
  whatever banks are `ready` and have local data.
- **Cost**: pricing is $0 for deterministic banks. LLM rewards cost is
  roughly $0.02 per card, so a new small bank adds cents per full run.
