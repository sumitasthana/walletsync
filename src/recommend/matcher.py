"""Match cards to a plain-language description of spending needs.

Deterministic scoring over the unified dataset: parse the needs text for
spending categories and modifiers, then score every card by its earn rates
on the matched categories, its base rate on general spend, its foreign
transaction fee for international use, and a small annual fee penalty.
No LLM involved; safe to call on every keystroke.
"""

import re
from typing import List, Optional

from src.banks import PROJECT_ROOT
from src.unified.build_unified import build_unified

CATEGORY_KEYWORDS = {
    "gas": ["gas", "fuel", "gasoline"],
    "groceries": ["grocer", "supermarket"],
    "dining": ["dining", "restaurant", "eat out", "eating out"],
    "travel": ["travel", "flight", "airline", "vacation", "airport"],
    "hotels": ["hotel"],
    "transit": ["transit", "train", "subway", "commute"],
    "streaming": ["streaming", "netflix", "spotify", "hulu"],
    "drugstores": ["drugstore", "pharmacy", "prescription"],
    "lyft": ["lyft"],
    "amazon": ["amazon"],
    "disney": ["disney"],
    "home_improvement": ["home improvement", "hardware", "home depot"],
    "car_rental": ["rental car", "car rental"],
    "rotating_5pct": ["rotating", "quarterly categories"],
}

INTERNATIONAL_KEYWORDS = [
    "abroad", "international", "overseas", "foreign transaction",
    "outside the country", "outside the us",
]

GENERAL_WEIGHT_WHEN_CATEGORIZED = 0.25

# Explicit destination, merchant, or loyalty-program requests need relevant
# candidates even when their benefits are not represented by an earn-rate row.
BRAND_KEYWORDS = {
    "disney": ["disney", "disneyland", "disneyworld"],
    "amazon": ["amazon"],
    "marriott": ["marriott", "bonvoy"],
    "hyatt": ["hyatt"],
    "ihg": ["ihg", "holiday inn", "intercontinental"],
    "united": ["united airlines", "united miles", "united card"],
    "southwest": ["southwest"],
    "aeroplan": ["aeroplan", "air canada"],
    "instacart": ["instacart"],
    "doordash": ["doordash"],
}


def _contains_term(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) is not None


def parse_needs(text: str) -> dict:
    """Parse a needs description into category weights and modifiers."""
    text_lower = (text or "").lower()
    categories = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text_lower for k in keywords):
            categories[category] = 1.0
    return {
        "categories": categories,
        "general": 1.0 if not categories else GENERAL_WEIGHT_WHEN_CATEGORIZED,
        "international": any(k in text_lower for k in INTERNATIONAL_KEYWORDS),
        "brands": [brand for brand, aliases in BRAND_KEYWORDS.items()
                   if any(_contains_term(text_lower, alias) for alias in aliases)],
    }


def load_catalog() -> List[dict]:
    """Load every card from the unified dataset with the fields the
    matcher and the UI need."""
    catalog = []
    for record in build_unified():
        info = record.get("card_info", {}) or {}
        meta = record.get("_meta", {}) or {}
        card_id = info.get("card_id")
        bank = info.get("bank") or meta.get("bank")
        if not card_id or not bank:
            continue
        rewards = record.get("rewards") or record.get("rewards_fallback") or {}
        pricing = record.get("pricing") or {}
        image = PROJECT_ROOT / "data" / bank / "images" / f"{card_id}.png"
        catalog.append({
            "card_id": card_id,
            "card_name": info.get("card_name"),
            "bank": bank,
            "reward_currency": info.get("reward_currency"),
            "annual_fee_usd": info.get("annual_fee_usd"),
            "base_earn_rate": info.get("base_earn_rate"),
            "earning_categories": rewards.get("earning_categories") or [],
            "foreign_transaction_fee_pct": pricing.get("foreign_transaction_fee_pct"),
            "data_quality_tier": meta.get("data_quality_tier"),
            "has_image": image.exists(),
        })
    return catalog


def score_card(card: dict, needs: dict) -> tuple:
    """Score one card against parsed needs. Returns (score, matched list)."""
    cats = {c["category"]: c for c in card["earning_categories"] or []}
    score = 0.0
    matched = []

    for category, weight in needs["categories"].items():
        ec = cats.get(category)
        if ec:
            score += weight * float(ec.get("rate", 0))
            matched.append({
                "category": category,
                "rate": ec.get("rate"),
                "cap_usd": ec.get("cap_usd"),
                "requires_activation": bool(ec.get("requires_activation")),
                "notes": ec.get("notes"),
            })

    base = card.get("base_earn_rate")
    if base is not None:
        score += needs["general"] * float(base)
        if not matched:
            matched.append({
                "category": "all_other",
                "rate": base,
                "cap_usd": None,
                "requires_activation": False,
            })

    if needs["international"]:
        ftf = card.get("foreign_transaction_fee_pct")
        if ftf is not None:
            score += (3.0 - float(ftf)) * 1.5

    fee = card.get("annual_fee_usd") or 0
    score -= float(fee) / 100.0

    return score, matched


def match_cards(text: str, top: int = 6,
                catalog: Optional[List[dict]] = None,
                bank: Optional[str] = None) -> List[dict]:
    """Rank cards against a needs description. Deterministic and local."""
    if catalog is None:
        catalog = load_catalog()
    needs = parse_needs(text)

    scored = []
    for card in catalog:
        if bank and card["bank"] != bank:
            continue
        score, matched = score_card(card, needs)
        scored.append({
            "card_id": card["card_id"],
            "card_name": card["card_name"],
            "bank": card["bank"],
            "reward_currency": card["reward_currency"],
            "annual_fee_usd": card["annual_fee_usd"],
            "base_earn_rate": card["base_earn_rate"],
            "foreign_transaction_fee_pct": card["foreign_transaction_fee_pct"],
            "data_quality_tier": card["data_quality_tier"],
            "has_image": card["has_image"],
            "score": round(score, 2),
            "matched": matched,
            "intent_matches": [brand for brand in needs["brands"]
                               if _contains_term((card.get("card_name") or "").lower(), brand)],
        })

    scored.sort(key=lambda c: (-len(c["intent_matches"]), -c["score"], -len(c["matched"]),
                               c["annual_fee_usd"] or 0))
    return scored[:top]
