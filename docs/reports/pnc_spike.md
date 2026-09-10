# PNC Spike Report

Investigation into onboarding PNC as the second bank. Scope was formats and
access only: no PNC pipeline code was built. This report is the decision
point for how PNC pricing should be extracted.

Date: 2026-09-09

## How this was investigated

Automated capture from this machine was blocked by PNC's bot protection
(details below), so page structure was analyzed from the live pages fetched
via a web proxy and from search-indexed PDF text. `scripts/investigate_pnc.py`
was written and kept so the capture can be re-run when access works. It saves
raw HTML under `data/pnc/spike/`.

## Finding 1: automated access is blocked (affects scraping only)

Every automated fetch method from this machine failed:

| Method | Result |
|---|---|
| Playwright headless Chromium | `net::ERR_HTTP2_PROTOCOL_ERROR` |
| Playwright Chromium with HTTP/2 disabled | navigation timeout |
| Plain `requests` (HTML page) | read timeout |
| Plain `requests` (rates PDF) | read timeout |

The pages themselves are public: the same URLs were fetched successfully
through a web proxy, and search engines index the PDF text. So the block is
specific to the client or network, not the content. Firefox is not installed
in the venv; it may behave differently but was not tested.

Impact: the scrape and dump stages cannot run unattended yet. Everything
downstream of raw captures (clean, parse, extract, merge, unified) already
works from local files, so PNC data can still be onboarded via manual
captures: save the card pages and PDFs into `data/pnc/` and run the pipeline
with `--bank pnc`. With only 4-6 PNC cards, a hand-maintained
`data/pnc/cards.json` manifest is a reasonable starting point.

## Finding 2: card lineup is small

Listing page: `https://www.pnc.com/en/personal-banking/banking/credit-cards.html`

| Card | Notes |
|---|---|
| PNC Cash Rewards Visa | 4% gas / 3% restaurants / 2% groceries, 1% other, $8,000 annual combined cap, $200 bonus after $1,000 in 3 months |
| PNC Cash Unlimited | flat 2% cash back, no foreign transaction fee, 0% intro BT APR 15 months |
| PNC Spend Wise | 0% intro APR on purchases and BT 18 months, purchase APR reduction program |
| PNC Secured Visa | branch-only application, still has Rates and Fees PDF |

PNC Core and PNC points exist but are not listed for online applications
(third-party sources), so they are out of scope initially.

Product pages follow a clean URL pattern:
`.../credit-cards/pnc-cash-rewards-visa-credit-card.html`. Card IDs generated
from these slugs would be readable and stable.

## Finding 3: pricing terms are PDFs, standard Schumer Box

Pricing format (the deferred decision):

- Every card links a "Rates and Fees" PDF, for example
  `https://www.pnc.com/content/dam/pnc-com/pdf/personal/CreditCards/cash-rewards-rates.pdf`
- The document is a standard "Important Information About Rates and Fees"
  Schumer Box, the same US CARD Act format Chase publishes as HTML
- Fields match `PricingExtended` exactly: purchase APR range (18.49% to
  28.49% variable, Prime-based), balance transfer APR with 0% intro for 15
  months when transferred within 90 days, cash advance APR, foreign
  transaction fee 3%, late fee up to $38, balance transfer fee 5% min $5
- The same PDF also embeds a reward program summary: 4% gas, 3% restaurants,
  2% groceries (first $8,000 combined annually), 1% other, with merchant
  category code qualification rules

### Recommendation for PNC pricing

Deterministic PDF parsing, gated on one validation step:

1. Manually download 2 PNC rates PDFs (browser save-as) into
   `data/pnc/spike/`.
2. Run `pdf_utils.download_and_extract_pdf_text` logic over the local files
   and check that PyMuPDF yields clean label and value lines for the Schumer
   rows.
3. If the text is clean, build a PDF row extractor that feeds the existing
   value parsers (`parse_apr_range`, `parse_intro_apr`, `parse_percent`,
   `parse_dollar_fee`), which are format-agnostic and already unit tested.
4. If the two-column PDF layout scrambles the text order, fall back to the
   Bedrock LLM path for PNC pricing only.

Rationale: consistent with the Path B philosophy (free, testable, no
hallucinations), and the risk is contained to the PNC adapter. The main
unknown, PDF text layout quality, cannot be checked from this machine because
downloads are blocked, hence the validation gate.

## Finding 4: rewards are PDFs too, and richer than expected

- Each card has a "Rewards Terms and Conditions" PDF separate from the rates
  PDF, plus the reward program summary embedded in the rates PDF
- Product pages carry redemption details: $25 minimum redemption, statement
  credit, direct deposit to PNC accounts, rewards never expire while open
- These map directly onto `RewardsExtended` fields (redemption_options,
  redemption_minimum_usd, points_expiration_months)
- PNC has no transfer partners, so `transfer_partners` would be an empty list
- Earning categories (gas, dining, groceries, all_other) are all already in
  `BASE_CATEGORIES`; no PNC category extensions needed initially

The existing tier 1 path (download PDF, extract text, Bedrock extraction)
applies unchanged. PNC cards would likely land in tier_1_pdf, giving better
rewards tier coverage than Chase (currently 13 of 41 tier 1).

## Finding 5: cleaning heuristics transfer

PNC marketing copy matches the existing `clean_data.py` regex patterns well:
"$0 Annual Fee", "Earn a $200 bonus after opening an account and making
$1,000 in purchases within the first 3 months", "1% cash back on all other
purchases". Only `extract_base_earn_rate`'s Chase partner keyword list and
`generate_card_id`'s path conventions need PNC variants.

## Effort estimate for the full PNC pipeline (next effort, not this one)

| Stage | Size | Notes |
|---|---|---|
| Card manifest + manual captures | small | 4 cards, hand-maintained cards.json, saved PDFs |
| clean_data PNC variants | small | id generation and rate keywords |
| Dump step for rates PDFs | small | reuse pdf_utils, read from local files |
| Pricing PDF parser | medium | gated on the validation step above |
| Rewards extraction | none | existing tier 1 LLM path works as-is |
| CLI / unified | none | already bank-aware; flip status to ready |

## Go / no-go

Go, with two conditions:

1. Pricing uses the deterministic PDF path only after the manual-download
   validation succeeds; otherwise LLM for PNC pricing.
2. Data collection starts with manual captures (or a network where PNC is
   reachable); unattended scraping needs separate bot-protection work that
   is out of scope here.
