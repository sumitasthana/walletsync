"""Comparison order must not turn placement or missing fields into an advantage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.recommend.comparison import comparison_matches, comparison_summary


def card(name, bank, rate, fee=0, currency="Cash Back"):
    return {"card_id": name, "card_name": name, "bank": bank, "reward_currency": currency,
            "annual_fee_usd": fee, "base_earn_rate": 1, "foreign_transaction_fee_pct": 0,
            "has_image": False, "data_quality_tier": "full",
            "earning_categories": [{"category": "gas", "rate": rate, "cap_usd": None}],
            "matched": [{"category": "gas", "rate": rate, "cap_usd": None}]}


def test_focus_precedes_stronger_alternatives_without_changing_scores():
    catalog = [card("Other", "new-bank", 5), card("PNC", "pnc", 2), card("PNC second", "pnc", 1)]
    cards = comparison_matches("gas", catalog=catalog)
    assert [c["card_id"] for c in cards] == ["PNC", "Other"]
    assert cards[0]["score"] < cards[1]["score"]
    summary = comparison_summary(cards, "gas")
    assert summary["impacts"][0]["direction"] == "negative"
    assert "$3 less per $100" in summary["impacts"][0]["detail"]


def test_tradeoffs_include_positive_negative_and_caps():
    focus, other = card("PNC", "pnc", 4, 95), card("Other", "other", 2)
    focus["matched"][0].update(cap_usd=1500, requires_activation=True)
    summary = comparison_summary([focus, other], "gas")
    assert [i["direction"] for i in summary["impacts"]] == ["positive", "negative"]
    assert "$2 more per $100" in summary["impacts"][0]["detail"]
    assert "$1500 spending cap" in summary["impacts"][0]["detail"]
    assert "activation required" in summary["impacts"][0]["detail"]
    assert "$95 more each year" in summary["impacts"][1]["detail"]


def test_points_and_missing_fees_do_not_become_cash_advantages():
    focus, other = card("PNC", "pnc", 5, None, "Points"), card("Other", "other", 2)
    summary = comparison_summary([focus, other], "gas")
    assert all(i["direction"] == "neutral" for i in summary["impacts"])
    assert all("per $100" not in i["detail"] for i in summary["impacts"])
    assert not any("annual" in i["title"].lower() for i in summary["impacts"])


def test_international_fees_only_when_relevant():
    focus, other = card("PNC", "pnc", 1), card("Other", "other", 1)
    focus["foreign_transaction_fee_pct"] = 3
    assert not any("abroad" in i["title"] for i in comparison_summary([focus, other], "gas")["impacts"])
    summary = comparison_summary([focus, other], "travel abroad")
    fee = next(i for i in summary["impacts"] if i["title"] == "Higher cost abroad")
    assert fee["direction"] == "negative"
    assert "$3 more in fees per $100" in fee["detail"]


def test_empty_or_single_card_has_no_invented_comparison():
    assert comparison_summary([], "gas") is None
    assert comparison_summary([card("PNC", "pnc", 4)], "gas") is None


def test_missing_category_rate_is_not_assumed_to_equal_base_rate():
    focus, other = card("PNC", "pnc", 4), card("Other", "other", 1)
    other["matched"] = []
    summary = comparison_summary([focus, other], "gas")
    assert not any("gas" in i["title"] for i in summary["impacts"])


def test_disney_request_keeps_focus_bank_but_prioritizes_disney_alternatives():
    generic = card("Generic", "chase", 1)
    disney = card("Disney Visa", "chase", 1, currency="Disney Rewards Dollars")
    focus = card("PNC", "pnc", 1)
    results = comparison_matches("Go to Disney", catalog=[generic, disney, focus], selected=[generic])
    assert [c["card_name"] for c in results] == ["PNC", "Disney Visa", "Generic"]
