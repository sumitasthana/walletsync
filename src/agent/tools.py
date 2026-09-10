"""LangChain tools for the WalletSync card terms agent.

Pure helper functions live at module level for testability. build_tools()
wraps them as LangChain tools and closes over the search backend.
"""

import json
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.banks import BANKS
from src.common import merge
from src.common.dump_utils import parse_frontmatter
from src.rag.embeddings import embed_text
from src.rag.store import search_chunks

MAX_DOC_CHARS = 60000


def find_bank_for_card(card_id: str):
    """Return the bank config that owns a card id, or None."""
    for key in sorted(BANKS):
        bank = BANKS[key]
        if not bank.cards_clean_path.exists():
            continue
        cards = merge.load_json_records(bank.cards_clean_path)
        if any(c.get("card_id") == card_id for c in cards):
            return bank
    return None


def load_card_documents(bank, card_id: str) -> str:
    """Load one card's raw pricing and rewards documents for the context."""
    parts = []
    pricing_path = bank.raw_pricing_dir / f"{card_id}.json"
    if pricing_path.exists():
        dump = json.loads(pricing_path.read_text(encoding="utf-8"))
        rows = dump.get("schumer_rows", {}) or {}
        if rows:
            parts.append("PRICING TERMS, Schumer Box rows:\n"
                         + "\n".join(f"- {k}: {v}" for k, v in rows.items()))
        full_text = dump.get("full_page_text", "")
        if full_text:
            parts.append("PRICING TERMS, full page text:\n" + full_text)
    rewards_path = bank.raw_rewards_dir / f"{card_id}.txt"
    if rewards_path.exists():
        _, body = parse_frontmatter(str(rewards_path))
        parts.append("REWARDS AGREEMENT, full text:\n" + body)
    return "\n\n".join(parts)[:MAX_DOC_CHARS]


def format_search_result(result: dict) -> str:
    """Render one search hit with its citation."""
    m = result["metadata"]
    cite = f"[{m.get('bank')} / {m.get('card_id')} / {m.get('doc_type')}"
    if m.get("section"):
        cite += f" / {m['section']}"
    cite += "]"
    return f"{cite}\n{result['text']}"


def build_tools(collection, embed_client):
    """Build the agent's tool set.

    collection and embed_client may be None (search then reports that the
    index is unavailable instead of failing).
    """

    class SearchInput(BaseModel):
        query: str = Field(description="What to look for, in the words the documents would use")
        card_id: Optional[str] = Field(default=None, description="Optional: restrict to one card")
        bank: Optional[str] = Field(default=None, description="Optional: restrict to one bank")
        k: int = Field(default=6, description="Number of chunks to return")

    @tool("search_documents", args_schema=SearchInput)
    def search_documents(query: str, card_id: Optional[str] = None,
                         bank: Optional[str] = None, k: int = 6) -> str:
        """Search the full text of card pricing terms, rewards agreements, and marketing copy. Use this for any question about card details."""
        if collection is None or embed_client is None:
            return "Search index not available. Run: python src/rag/build_index.py"
        where = {}
        if card_id:
            where["card_id"] = card_id
        if bank:
            where["bank"] = bank
        try:
            embedding = embed_text(embed_client, query)
            results = search_chunks(collection, embedding, k=k, where=where or None)
        except Exception as e:
            return f"Search failed: {e}"
        if not results:
            return "No matching documents found."
        return "\n\n".join(format_search_result(r) for r in results)

    @tool
    def get_card(card_id: str) -> str:
        """Get the structured pricing and rewards record for one card (APRs, fees, earning categories)."""
        bank = find_bank_for_card(card_id)
        if not bank:
            return f"Unknown card id: {card_id}"
        card = merge.find_record(merge.load_json_records(bank.cards_clean_path), card_id)
        pricing = merge.find_record(merge.load_json_records(bank.extracted_pricing_path), card_id)
        rewards = merge.find_record(merge.load_json_records(bank.extracted_rewards_path), card_id)
        return json.dumps({"card_info": card, "pricing": pricing, "rewards": rewards},
                          indent=1, ensure_ascii=False, default=str)

    @tool
    def get_pricing_field(field: str, bank: Optional[str] = None) -> str:
        """Get one pricing field for all cards at once, from the structured extracted records. Use this for 'which cards' questions about fees or APRs. Fields include: foreign_transaction_fee_pct, late_payment_fee_max_usd, purchase_apr_min, purchase_apr_max, cash_advance_apr, penalty_apr_max, balance_transfer_fee_pct, cash_advance_fee_pct, purchase_apr_intro_pct, purchase_apr_intro_months, bt_apr_intro_months, authorized_user_fee_usd."""
        lines = []
        for key in sorted(BANKS):
            if bank and key != bank:
                continue
            b = BANKS[key]
            if not b.extracted_pricing_path.exists():
                continue
            for r in merge.load_json_records(b.extracted_pricing_path):
                if field in r:
                    lines.append(f"{key} / {r.get('card_id')}: {r.get(field)}")
        if not lines:
            return f"Unknown field or no data: {field}"
        return "\n".join(lines)

    @tool
    def list_cards(bank: Optional[str] = None) -> str:
        """List card ids and names only. Contains no fee, APR, or rewards detail; do not use it to answer questions about card terms."""
        out = []
        for key in sorted(BANKS):
            if bank and key != bank:
                continue
            b = BANKS[key]
            if not b.cards_clean_path.exists():
                continue
            for c in merge.load_json_records(b.cards_clean_path):
                out.append(f"{key}: {c.get('card_id')} - {c.get('card_name')}")
        return "\n".join(out) or "No cards found."

    @tool
    def recommend_cards(needs: str, top: int = 6) -> str:
        """Rank credit cards against a plain-language description of the user's spending needs (for example 'I spend a lot on gas and groceries'). Returns scored matches with the earn rates that matched. Use this whenever the user asks which card fits them."""
        from src.recommend.matcher import match_cards
        return json.dumps(match_cards(needs, top=top), ensure_ascii=False, default=str)

    return [search_documents, get_card, get_pricing_field, recommend_cards, list_cards]
