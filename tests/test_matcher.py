"""Tests for the card matcher."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.recommend.matcher import match_cards, parse_needs


def test_parse_needs_categories():
    needs = parse_needs("I commute a lot, mostly gas and groceries, dining out on weekends")
    assert needs["categories"]["gas"] == 1.0
    assert needs["categories"]["groceries"] == 1.0
    assert needs["categories"]["dining"] == 1.0
    assert needs["general"] < 1.0
    assert not needs["international"]


def test_parse_needs_international():
    needs = parse_needs("I travel abroad frequently")
    assert needs["categories"]["travel"] == 1.0
    assert needs["international"]


def test_parse_needs_empty():
    needs = parse_needs("")
    assert needs["categories"] == {}
    assert needs["general"] == 1.0


def test_match_gas_groceries_favors_pnc():
    results = match_cards("gas and groceries", top=5)
    assert results
    top_ids = [r["card_id"] for r in results]
    assert "pnc-cash-rewards-visa-credit-card-0e8451" in top_ids[:2]
    top = results[0]
    assert top["score"] >= results[-1]["score"]
    matched = {m["category"]: m["rate"] for m in top["matched"]}
    assert "gas" in matched or "groceries" in matched


def test_match_dining_includes_freedom_flex():
    results = match_cards("dining out a lot", top=5)
    ids = [r["card_id"] for r in results]
    assert "freedom-flex-a6950e" in ids[:2]
    ff = next(r for r in results if r["card_id"] == "freedom-flex-a6950e")
    assert any(m["category"] == "dining" and m["rate"] == 3.0 for m in ff["matched"])


def test_match_scores_sorted():
    results = match_cards("travel and hotels", top=8)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_match_records_have_ui_fields():
    results = match_cards("streaming", top=3)
    for r in results:
        assert r["card_id"] and r["card_name"] and r["bank"]
        assert isinstance(r["matched"], list)
        assert isinstance(r["has_image"], bool)
        assert r["data_quality_tier"]


def test_named_destination_includes_relevant_cards_before_generic_rewards():
    results = match_cards("I want to go to Disney -- which card would fit", top=6)
    disney = next(c for c in results[:3] if c["card_id"] == "disney-rewards-fa5408")
    assert disney["intent_matches"] == ["disney"]
    assert disney["reward_currency"] == "Disney Rewards Dollars"
    assert disney["base_earn_rate"] == 1.0


def test_brand_relevance_generalizes_beyond_disney():
    results = match_cards("I stay at Marriott hotels", top=3)
    assert all("marriott" in r["intent_matches"] for r in results)
    assert parse_needs("I want to visit Disneyland")["brands"] == ["disney"]
