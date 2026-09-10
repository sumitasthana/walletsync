"""API regression tests. Agent responses are mocked; no AWS requests are made."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.web import app as web


@pytest.fixture
def client():
    return web.app.test_client()


@pytest.mark.parametrize("endpoint,body", [
    ("match", []), ("match", {"text": 4}), ("match", {"top": "6"}),
    ("match", {"top": -1}), ("match", {"top": True}),
    ("chat", {"message": ["hi"]}), ("chat", {"message": " "}),
    ("chat", {"message": "hi", "history": "bad"}),
    ("chat", {"message": "hi", "history": [None]}),
    ("chat", {"message": "hi", "history": [{"role": "system", "content": "hi"}]}),
])
def test_invalid_body_returns_json(client, endpoint, body):
    response = client.post(f"/api/{endpoint}", json=body)
    assert response.status_code == 400
    assert response.json["error"]


def test_live_matches_and_blank_input(client):
    response = client.post("/api/match", json={"text": "gas and groceries", "top": 3})
    assert response.status_code == 200
    assert len(response.json["matches"]) == 3
    assert response.json["matches"][0]["bank"] == "pnc"
    assert all(c["bank"] != "pnc" for c in response.json["matches"][1:])
    assert response.json["comparison"]["card_id"] == response.json["matches"][0]["card_id"]
    assert client.post("/api/match", json={"text": " "}).json == {"matches": [], "comparison": None}


def test_agent_failure_returns_live_matches_without_exception_details(client, monkeypatch):
    agent = Mock()
    agent.invoke.side_effect = RuntimeError("secret-provider-detail")
    monkeypatch.setattr(web, "get_agent", lambda: agent)
    response = client.post("/api/chat", json={"message": "gas"})
    assert response.status_code == 503
    assert response.json["cards"]
    assert response.json["source"] == "live"
    assert response.json["reply"] == ""
    assert "secret-provider-detail" not in response.get_data(as_text=True)


def test_agent_cards_and_content_blocks(client, monkeypatch):
    cards = [{"card_id": "test-card"}]
    def invoke(state):
        return {"messages": state["messages"] + [
            ToolMessage(content=json.dumps(cards), name="recommend_cards", tool_call_id="call-1"),
            AIMessage(content=[{"type": "text", "text": "Here are your cards."}]),
        ]}
    monkeypatch.setattr(web, "get_agent", lambda: SimpleNamespace(invoke=invoke))
    response = client.post("/api/chat", json={"message": "gas"})
    assert response.status_code == 200
    assert response.json["cards"] == cards
    assert response.json["source"] == "agent"
    assert response.json["reply"] == "Here are your cards."


def test_chat_keeps_alternatives_when_last_tool_only_returned_focus_bank(client, monkeypatch):
    focus = web.match_cards("gas and groceries", top=1)
    def invoke(state):
        return {"messages": state["messages"] + [
            ToolMessage(content=json.dumps(focus), name="recommend_cards", tool_call_id="call-1"),
            AIMessage(content="Here are the benefits and tradeoffs."),
        ]}
    monkeypatch.setattr(web, "get_agent", lambda: SimpleNamespace(invoke=invoke))
    response = client.post("/api/chat", json={"message": "gas and groceries"})
    assert response.status_code == 200
    assert response.json["cards"][0]["bank"] == "pnc"
    assert len(response.json["cards"]) == 6
    assert all(c["bank"] != "pnc" for c in response.json["cards"][1:])
    assert response.json["comparison"]["alternative_name"]


def test_no_answer_does_not_repeat_old_assistant_message(client, monkeypatch):
    monkeypatch.setattr(web, "get_agent", lambda: SimpleNamespace(invoke=lambda state: state))
    response = client.post("/api/chat", json={"message": "gas", "history": [
        {"role": "assistant", "content": "Old answer"},
    ]})
    assert response.status_code == 503
    assert response.json["reply"] == ""


def test_fallback_uses_previous_spending_needs(client, monkeypatch):
    monkeypatch.setattr(web, "get_agent", lambda: SimpleNamespace(invoke=lambda state: {
        "messages": state["messages"] + [AIMessage(content="Let me explain.")]
    }))
    matcher = Mock(return_value=[])
    monkeypatch.setattr(web, "match_cards", matcher)
    response = client.post("/api/chat", json={"message": "why?", "history": [
        {"role": "user", "content": "gas and groceries"},
        {"role": "assistant", "content": "Here is a match."},
    ]})
    assert response.status_code == 200
    matcher.assert_called_once_with("gas and groceries\nwhy?", top=6)


def test_images_reject_unknown_banks(client):
    assert client.get("/card-images/unknown/card.png").status_code == 404


def test_answers_use_card_names_even_if_the_model_returns_an_id(client, monkeypatch):
    monkeypatch.setattr(web, "get_agent", lambda: SimpleNamespace(invoke=lambda state: {
        "messages": state["messages"] + [AIMessage(
            content="Consider marriott-bonvoy-boundless-58772b for your hotel spending."
        )]
    }))
    response = client.post("/api/chat", json={"message": "Which hotel card fits?"})
    assert response.status_code == 200
    reply = response.json["reply"]
    assert "marriott-bonvoy-boundless-58772b" not in reply
    assert "Marriott Bonvoy Boundless" in reply
    assert reply.endswith("for your hotel spending.")


def test_empty_agent_recommendations_clear_previous_cards(client, monkeypatch):
    def invoke(state):
        return {"messages": state["messages"] + [
            ToolMessage(content="[]", name="recommend_cards", tool_call_id="call-1"),
            AIMessage(content="No cards match those requirements."),
        ]}
    monkeypatch.setattr(web, "get_agent", lambda: SimpleNamespace(invoke=invoke))
    matcher = Mock()
    monkeypatch.setattr(web, "match_cards", matcher)
    response = client.post("/api/chat", json={"message": "no cards"})
    assert response.status_code == 200
    assert response.json["cards"] == []
    assert response.json["source"] == "agent"
    matcher.assert_not_called()
