# Quick Start Guide

## Prerequisites

1. **Python 3.10+** installed
2. **AWS Account** with Bedrock access (for fee extraction)

## Setup (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure AWS (for Bedrock)
Create `.env` file in project root:
```env
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1
```

## Run the Pipeline

### Option A: Full Pipeline
```bash
# Step 1: Scrape Chase credit cards (takes ~2 min)
python src/chase_scraper.py

# Step 2: Clean and transform data (instant)
python src/clean_data.py

# Step 3: Extract fees with Bedrock (takes ~40 sec for 3 cards)
python src/extract_fees_bedrock.py
```

### Option B: Individual Steps

**Just scrape cards:**
```bash
python src/chase_scraper.py
# Output: output/chase_cards.json (82 cards)
```

**Just clean data:**
```bash
python src/clean_data.py
# Output: output/chase_cards_clean.json (structured data)
```

**Just extract fees:**
```bash
python src/extract_fees_bedrock.py
# Output: output/extracted_fees.json (fee data)
```

## Output Files

After running all steps:

```
output/
├── chase_cards.json              # Raw scraped data (85 KB)
├── chase_cards_clean.json        # Cleaned data (37 KB)
└── extracted_fees.json           # Fee data (1 KB)
```

## Common Tasks

### View scraped cards
```bash
# Windows PowerShell
Get-Content output/chase_cards_clean.json | ConvertFrom-Json | Select-Object -First 5

# Or open in any text editor
```

### Process all cards with Bedrock
Edit `src/extract_fees_bedrock.py` line ~240:
```python
# Change this:
test_cards = cards_with_pricing[:3]

# To this:
test_cards = cards_with_pricing
```

### Check Bedrock costs
- **3 cards:** ~$0.002
- **41 cards:** ~$0.03
- **82 cards:** ~$0.06

## Troubleshooting

### "Unable to locate credentials"
- Ensure `.env` file exists in project root
- Check AWS credentials are valid
- Verify Bedrock access in your AWS account

### "Playwright not found"
```bash
playwright install chromium
```

### "Module not found"
```bash
pip install -r requirements.txt
```

### Scraping fails
- Check internet connection
- Chase website may be down
- Try again in a few minutes

## What's Next?

1. ✅ **Scraped 82 cards** with basic info
2. ✅ **Cleaned data** with typed fields
3. ✅ **Extracted fees** for 3 test cards
4. 🔄 **Scale to all cards** - Remove `[:3]` limit
5. 🔄 **Merge datasets** - Combine fees with main data
6. 🔄 **Build comparisons** - Create card comparison tool

## Need Help?

- Check `README.md` for detailed documentation
- See `PROJECT_STRUCTURE.md` for architecture
- Review `output/BEDROCK_EXTRACTION_SUMMARY.md` for Bedrock details
