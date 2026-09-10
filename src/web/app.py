"""WalletSync chat UI: a terminal-style chat with live card matching.

Run:
    python src/web/app.py
Then open http://127.0.0.1:5000

Typing in the chat input live-updates the matches panel through the
deterministic matcher (no LLM). Sending the message hands the conversation
to the LangGraph agent, which explains its picks; the cards it recommended
are rendered in the same panel.
"""

import json
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.banks import PROJECT_ROOT
from src.rag.embeddings import get_embedding_client
from src.rag.store import get_collection
from src.recommend.matcher import match_cards

load_dotenv()

app = Flask(__name__)

AGENT = None


def get_agent():
    """Build the LangGraph agent once; search is enabled when indexed."""
    global AGENT
    if AGENT is None:
        from src.agent.graph import build_agent
        collection = None
        embed_client = None
        try:
            collection = get_collection()
            if collection.count() == 0:
                collection = None
            else:
                embed_client = get_embedding_client()
        except Exception:
            collection = None
        AGENT = build_agent(collection=collection, embed_client=embed_client)
    return AGENT


def message_text(m) -> str:
    if isinstance(m.content, list):
        return "".join(p.get("text", "") for p in m.content if isinstance(p, dict))
    return str(m.content)


def extract_recommendations(messages) -> list:
    """Pull the cards the agent recommended from its tool results."""
    cards = []
    for m in messages:
        if isinstance(m, ToolMessage) and getattr(m, "name", "") == "recommend_cards":
            try:
                parsed = json.loads(m.content)
                if isinstance(parsed, list) and parsed:
                    cards = parsed
            except (json.JSONDecodeError, TypeError):
                continue
    return cards


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/card-images/<bank>/<path:filename>")
def card_image(bank, filename):
    return send_from_directory(Path(PROJECT_ROOT) / "data" / bank / "images", filename)


@app.route("/api/match", methods=["POST"])
def api_match():
    data = request.get_json(force=True) or {}
    return jsonify({"matches": match_cards(data.get("text", ""),
                                           top=data.get("top", 6))})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True) or {}
    message = (data.get("message") or "").strip()
    history = (data.get("history") or [])[-12:]
    if not message:
        return jsonify({"reply": "", "cards": []})

    msgs = []
    for m in history:
        if m.get("role") == "user":
            msgs.append(HumanMessage(content=m.get("content", "")))
        elif m.get("role") == "assistant":
            msgs.append(AIMessage(content=m.get("content", "")))
    msgs.append(HumanMessage(content=message))

    reply = ""
    cards = []
    try:
        result = get_agent().invoke({"messages": msgs})
        for m in reversed(result["messages"]):
            if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
                reply = message_text(m)
                break
        cards = extract_recommendations(result["messages"])
    except Exception as e:
        reply = f"Agent error: {e}"

    if not cards:
        cards = match_cards(message, top=6)

    return jsonify({"reply": reply, "cards": cards})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
