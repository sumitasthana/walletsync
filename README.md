# WalletSync – Chase Credit Card Scraper

Extracts credit card data from Chase's public all-cards page using Playwright.

## Project Structure

```
WalletSync/
├── src/
│   └── chase_scraper.py      # Main scraping script
├── output/
│   ├── chase_cards.json      # Extracted data (82 cards)
│   ├── page_dump.html        # Raw HTML snapshot
│   └── summary.txt           # Execution summary
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

### 1. Scrape Data
```bash
python src/chase_scraper.py
```
Results saved to `output/chase_cards.json` (raw HTML text).

### 2. Clean & Transform Data
```bash
python src/clean_data.py
```
Produces `output/chase_cards_clean.json` with structured, typed fields:
- Extracts numerical values from text
- Classifies reward types (Cash Back/Points/Miles)
- Parses sign-up bonus details
- Converts to proper data types (Integer, Float, Boolean)
- **60% smaller file size**

### 3. Extract Fee Data (AWS Bedrock)
```bash
python src/extract_fees_bedrock.py
```
Mines structured fee data from pricing terms using Claude 3 Haiku:
- Scrapes Schumer Box tables from pricing URLs
- Converts HTML to Markdown
- Extracts fees via LLM tool calling
- Outputs typed JSON (foreign transaction fee, balance transfer fee, late fee, cash advance APR)
- **~$0.0007 per card** using Claude 3 Haiku

### 4. Extract Reward Rules (AWS Bedrock + PDF)
```bash
python src/extract_reward_rules_bedrock.py
```
Extracts reward constraints from PDF agreements using Claude 3 Haiku:
- Downloads PDF rewards agreements
- Extracts text using PyMuPDF
- Mines constraints via LLM tool calling
- Outputs typed JSON (category exclusions, expiration policy, redemption minimum, bonus rules)
- **~$0.0016 per card** using Claude 3 Haiku

**Prerequisites:** AWS credentials in `.env` file with Bedrock access

## Latest Execution

**Date:** April 21, 2026  
**Status:** ✓ Success  
**Cards Extracted:** 82  
**Output Size:** 85 KB

All cards successfully scraped with complete data including:
- Card names, URLs, annual fees, APR info
- Marketing tags, bonus offers, earning rates
- Pricing terms and rewards agreement links
