"""The CLI bank restriction must apply to every data access tool."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.agent import tools, toc_chat


def test_scoped_tools_cannot_access_other_banks():
    scoped = {tool.name: tool for tool in tools.build_tools(None, None, bank_scope="pnc")}
    assert "chase:" not in scoped["list_cards"].invoke({"bank": "chase"})
    assert "chase /" not in scoped["get_pricing_field"].invoke({"bank": "chase", "field": "purchase_apr_min"})
    assert "outside" in scoped["get_card"].invoke({"card_id": "freedom-flex-a6950e"})
    cards = json.loads(scoped["recommend_cards"].invoke({"needs": "gas and dining", "bank": "chase"}))
    assert cards and all(card["bank"] == "pnc" for card in cards)


def test_comparison_can_request_pnc_candidates():
    unscoped = {tool.name: tool for tool in tools.build_tools(None, None)}
    cards = json.loads(unscoped["recommend_cards"].invoke({"needs": "gas and groceries", "bank": "pnc"}))
    assert cards and all(card["bank"] == "pnc" for card in cards)


def test_search_applies_scope_even_when_model_requests_another_bank(monkeypatch):
    search = Mock(return_value=[])
    monkeypatch.setattr(tools, "embed_text", lambda client, query: [0.1])
    monkeypatch.setattr(tools, "search_chunks", search)
    scoped = {tool.name: tool for tool in tools.build_tools(object(), object(), bank_scope="pnc")}
    scoped["search_documents"].invoke({"query": "fees", "bank": "chase"})
    assert search.call_args.kwargs["where"] == {"bank": "pnc"}


def test_cli_passes_bank_to_agent(monkeypatch):
    build = Mock()
    monkeypatch.setattr(toc_chat, "build_agent", build)
    monkeypatch.setattr(toc_chat, "get_collection", lambda: SimpleNamespace(count=lambda: 3))
    monkeypatch.setattr(toc_chat, "get_embedding_client", lambda: object())
    monkeypatch.setattr("builtins.input", lambda prompt: "exit")
    toc_chat.chat(SimpleNamespace(card_id=None, bank="pnc", model="test-model"))
    assert build.call_args.kwargs["bank"] == "pnc"
