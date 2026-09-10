"""WalletSync React UI and chat API with live card matching.

Run:
    npm --prefix frontend ci
    npm --prefix frontend run build
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

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.banks import BANKS, PROJECT_ROOT
from src.agent.presentation import customer_card_names
from src.rag.embeddings import get_embedding_client
from src.rag.store import get_collection
from src.recommend.comparison import comparison_matches as match_cards, comparison_summary

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
FRONTEND_DIR = Path(__file__).parent / "static" / "app"

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


def extract_recommendations(messages) -> list | None:
    """Pull the cards the agent recommended from its tool results."""
    cards = None
    for m in messages:
        if isinstance(m, ToolMessage) and getattr(m, "name", "") == "recommend_cards":
            try:
                parsed = json.loads(m.content)
                if isinstance(parsed, list):
                    cards = parsed
            except (json.JSONDecodeError, TypeError):
                continue
    return cards


@app.route("/")
def index():
    if not (FRONTEND_DIR / "index.html").exists():
        return "Build the frontend first: npm --prefix frontend ci && npm --prefix frontend run build", 503
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/card-images/<bank>/<path:filename>")
def card_image(bank, filename):
    if bank not in BANKS:
        abort(404)
    return send_from_directory(Path(PROJECT_ROOT) / "data" / bank / "images", filename)


def json_body():
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest("Expected a JSON object.")
    return data


@app.errorhandler(BadRequest)
@app.errorhandler(UnsupportedMediaType)
def invalid_request(error):
    return jsonify({"error": "Invalid request. Send a JSON object with valid fields."}), error.code


@app.route("/api/match", methods=["POST"])
def api_match():
    data = json_body()
    text, top = data.get("text", ""), data.get("top", 6)
    if not isinstance(text, str) or len(text) > 8000:
        raise BadRequest()
    if type(top) is not int or not 1 <= top <= 12:
        raise BadRequest()
    cards = match_cards(text, top=top) if text.strip() else []
    return jsonify({"matches": cards, "comparison": comparison_summary(cards, text)})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = json_body()
    message, history = data.get("message", ""), data.get("history", [])
    if not isinstance(message, str) or len(message) > 8000:
        raise BadRequest()
    if not isinstance(history, list) or any(
        not isinstance(m, dict) or m.get("role") not in ("user", "assistant")
        or not isinstance(m.get("content"), str) or len(m["content"]) > 16000
        for m in history
    ):
        raise BadRequest()
    message, history = message.strip(), history[-12:]
    if not message:
        raise BadRequest()

    msgs = []
    for m in history:
        if m.get("role") == "user":
            msgs.append(HumanMessage(content=m.get("content", "")))
        elif m.get("role") == "assistant":
            msgs.append(AIMessage(content=m.get("content", "")))
    msgs.append(HumanMessage(content=message))

    reply = ""
    cards = None
    source = "agent"
    error = None
    try:
        result = get_agent().invoke({"messages": msgs})
        new_messages = result["messages"][len(msgs):]
        for m in reversed(new_messages):
            if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
                reply = customer_card_names(message_text(m))
                break
        if not reply:
            raise RuntimeError("Agent returned no answer")
        cards = extract_recommendations(new_messages)
    except Exception:
        app.logger.exception("Chat agent failed")
        error = "The assistant is unavailable. You can still explore live card matches. Please try again."
        reply = ""

    needs = "\n".join(m["content"] for m in history if m["role"] == "user") + "\n" + message
    if cards is None:
        cards = match_cards(needs, top=6)
        source = "live"
    elif cards and all(c.get("bank") and c.get("card_name") for c in cards):
        cards = match_cards(needs, top=6, selected=cards)

    return jsonify({"reply": reply, "cards": cards, "source": source, "error": error,
                    "comparison": comparison_summary(cards, needs)}), 503 if error else 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
