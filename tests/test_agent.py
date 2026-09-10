"""Tests for the LangGraph agent tools and graph assembly."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.tools import (
    build_tools,
    find_bank_for_card,
    format_search_result,
    load_card_documents,
)


def test_build_tools_count():
    tools = build_tools(None, None)
    assert len(tools) == 5
    assert {t.name for t in tools} == {
        "search_documents", "get_card", "get_pricing_field",
        "recommend_cards", "list_cards"
    }


def test_find_bank_for_card():
    assert find_bank_for_card("freedom-flex-a6950e").key == "chase"
    assert find_bank_for_card("pnc-cash-rewards-visa-credit-card-0e8451").key == "pnc"
    assert find_bank_for_card("nope") is None


def test_format_search_result():
    r = {"text": "Late Payment: Up to $40",
         "metadata": {"bank": "chase", "card_id": "x", "card_name": "Card",
                      "doc_type": "schumer_box", "section": "Late Payment",
                      "source_url": ""}}
    out = format_search_result(r)
    assert "[chase / x / schumer_box / Late Payment]" in out
    assert "Up to $40" in out


def test_get_pricing_field_tool():
    tools = {t.name: t for t in build_tools(None, None)}
    result = tools["get_pricing_field"].invoke(
        {"field": "foreign_transaction_fee_pct", "bank": "chase"})
    assert "freedom-flex-a6950e" in result
    assert ": 3.0" in result or ": 0.0" in result


def test_list_cards_tool():
    tools = {t.name: t for t in build_tools(None, None)}
    result = tools["list_cards"].invoke({"bank": "pnc"})
    assert "pnc-cash-rewards-visa-credit-card-0e8451" in result


def test_get_card_tool():
    tools = {t.name: t for t in build_tools(None, None)}
    result = tools["get_card"].invoke({"card_id": "freedom-flex-a6950e"})
    assert "foreign_transaction_fee_pct" in result


def test_recommend_cards_tool():
    tools = {t.name: t for t in build_tools(None, None)}
    result = tools["recommend_cards"].invoke({"needs": "gas and groceries"})
    parsed = json.loads(result)
    assert any("pnc-cash-rewards" in c["card_id"] for c in parsed)


def test_search_reports_missing_index():
    tools = {t.name: t for t in build_tools(None, None)}
    result = tools["search_documents"].invoke({"query": "foreign transaction fee"})
    assert "build_index" in result


def test_load_card_documents():
    bank = find_bank_for_card("freedom-flex-a6950e")
    docs = load_card_documents(bank, "freedom-flex-a6950e")
    assert "PRICING TERMS" in docs
    assert "REWARDS AGREEMENT" in docs


def test_agent_graph_compiles():
    from src.agent.graph import build_agent
    agent = build_agent(collection=None, embed_client=None)
    assert agent is not None
    assert hasattr(agent, "invoke")
