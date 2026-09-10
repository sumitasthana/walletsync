"""Tests for the unified dataset builder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.unified.build_unified import build_unified, data_quality_tier


def test_unified_contains_all_chase_cards():
    unified = build_unified()
    chase_cards = [c for c in unified if c["card_info"].get("bank") == "chase"]
    assert len(chase_cards) == 41


def test_unified_records_have_bank_and_tier():
    unified = build_unified()
    assert unified
    for record in unified:
        assert record["card_info"]["bank"]
        assert record["_meta"]["data_quality_tier"] in ("tier_1_pdf", "tier_2_html", "tier_3_none")


def test_unified_pricing_merged():
    unified = build_unified()
    ff = next(c for c in unified if c["card_info"]["card_id"] == "freedom-flex-a6950e")
    assert "pricing" in ff
    assert ff["pricing"]["purchase_apr_min"] == 18.24


def test_unified_tier_assignment():
    unified = build_unified()
    ff = next(c for c in unified if c["card_info"]["card_id"] == "freedom-flex-a6950e")
    assert ff["_meta"]["data_quality_tier"] == "tier_1_pdf"


def test_data_quality_tier_rules():
    assert data_quality_tier(None, {"card_id": "x"}, None) == "tier_1_pdf"
    assert data_quality_tier(None, None, {"card_id": "x"}) == "tier_2_html"
    assert data_quality_tier({"card_id": "x"}, None, None) == "tier_3_none"
    assert data_quality_tier(None, None, None) == "tier_3_none"
