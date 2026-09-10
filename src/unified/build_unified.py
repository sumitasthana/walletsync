"""Build the unified cross-bank card dataset.

Merges every ready bank's cleaned cards with their extracted pricing and
rewards data into data/unified/all_cards.json, with a bank field on every
record and a data quality tier per docs/DATA_QUALITY_TIERS.md.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.banks import BANKS, PROJECT_ROOT
from src.common import merge


def data_quality_tier(pricing, rewards, fallback):
    """Assign the data quality tier for one card."""
    if rewards:
        return "tier_1_pdf"
    if fallback:
        return "tier_2_html"
    return "tier_3_none"


def build_unified() -> list:
    """Build the unified dataset in memory (no file writes).

    Includes every bank that has cleaned card data, regardless of pipeline
    status; banks still in investigation simply contribute less detail.
    """
    unified = []
    for key in sorted(BANKS):
        bank = BANKS[key]
        if not bank.cards_clean_path.exists():
            continue
        cards = merge.load_json_records(bank.cards_clean_path)
        pricing = merge.load_json_records(bank.extracted_pricing_path)
        rewards = merge.load_json_records(bank.extracted_rewards_path)
        fallback = merge.load_json_records(bank.extracted_fallback_path)
        for card in cards:
            card_id = card.get("card_id")
            p = merge.find_record(pricing, card_id)
            r = merge.find_record(rewards, card_id)
            f = merge.find_record(fallback, card_id)
            record = merge.merge_card(card, p, r, f)
            record["_meta"]["data_quality_tier"] = data_quality_tier(p, r, f)
            unified.append(record)
    return unified


def write_unified() -> Path:
    """Build the unified dataset, write it, and print a coverage summary."""
    unified = build_unified()

    out_dir = PROJECT_ROOT / "data" / "unified"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "all_cards.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unified, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(unified)} cards to {out_path}")
    for key in sorted(BANKS):
        bank = BANKS[key]
        bank_cards = [c for c in unified if c["card_info"].get("bank") == key]
        if not bank_cards:
            print(f"  {key}: skipped ({bank.status})")
            continue
        with_pricing = sum(1 for c in bank_cards if "pricing" in c)
        tiers = {}
        for c in bank_cards:
            t = c["_meta"]["data_quality_tier"]
            tiers[t] = tiers.get(t, 0) + 1
        tier_str = ", ".join(f"{t}: {n}" for t, n in sorted(tiers.items()))
        print(f"  {key}: {len(bank_cards)} cards, {with_pricing} with pricing ({tier_str})")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build the unified cross-bank card dataset")
    args = parser.parse_args()
    write_unified()


if __name__ == "__main__":
    main()
