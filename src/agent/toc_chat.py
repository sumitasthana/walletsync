"""Agentic chat over card terms and conditions.

Single-card mode puts that card's documents directly in context, so it works
without a search index:

    python src/agent/toc_chat.py --card-id freedom-flex-a6950e

Bank or all-cards mode answers with retrieval over the vector index:

    python src/agent/toc_chat.py --bank chase
    python src/agent/toc_chat.py

Build the index first with: python src/rag/build_index.py
Type 'exit' to quit.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.banks import BANKS, get_bank
from src.common import merge
from src.common.dump_utils import parse_frontmatter
from src.rag.embeddings import embed_text, get_embedding_client
from src.rag.store import get_collection, search_chunks

MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
MAX_DOC_CHARS = 60000

SYSTEM_PROMPT = """You are WalletSync's card terms assistant. You explain credit
card pricing terms and rewards agreements in plain language.

Rules:
- Ground every number and claim in the tool results or the provided
  documents. Never invent rates, fees, or rules.
- For any question about card terms (fees, APRs, earning categories,
  program rules), you MUST call search_documents. Card names and marketing
  blurbs are not evidence of what a card charges; only retrieved pricing
  terms and agreement text count. Use list_cards only to look up ids.
- For 'which cards' questions about a fee or APR, prefer get_pricing_field:
  it returns exact structured values for every card at once.
- When you state a fact, name the source: bank, card, and document, for
  example [chase / freedom-flex-a6950e / schumer_box / Late Payment].
- If the documents do not answer the question, say so plainly. Do not
  guess from card names or partial information.
- Use short sentences and everyday words. Explain jargon when it appears.
- Keep answers brief unless the user asks for detail.
"""

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "search_documents",
                "description": "Search the full text of card pricing terms, rewards agreements, and marketing copy. Use this for any question about card details.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "What to look for, in the words the documents would use"},
                            "card_id": {"type": "string", "description": "Optional: restrict to one card"},
                            "bank": {"type": "string", "description": "Optional: restrict to one bank"},
                            "k": {"type": "integer", "description": "Number of chunks to return, default 6"},
                        },
                        "required": ["query"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_card",
                "description": "Get the structured pricing and rewards record for one card (APRs, fees, earning categories).",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"card_id": {"type": "string"}},
                        "required": ["card_id"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_pricing_field",
                "description": "Get one pricing field for all cards at once, from the structured extracted records. Use this for 'which cards' questions about fees or APRs. Fields include: foreign_transaction_fee_pct, late_payment_fee_max_usd, purchase_apr_min, purchase_apr_max, cash_advance_apr, penalty_apr_max, balance_transfer_fee_pct, cash_advance_fee_pct, purchase_apr_intro_pct, purchase_apr_intro_months, bt_apr_intro_months, authorized_user_fee_usd.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "description": "Field name from the pricing record"},
                            "bank": {"type": "string", "description": "Optional bank key"},
                        },
                        "required": ["field"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "list_cards",
                "description": "List card ids and names only. Contains no fee, APR, or rewards detail; do not use it to answer questions about card terms.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"bank": {"type": "string", "description": "Optional bank key"}},
                    }
                },
            }
        },
    ]
}


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
    m = result["metadata"]
    cite = f"[{m.get('bank')} / {m.get('card_id')} / {m.get('doc_type')}"
    if m.get("section"):
        cite += f" / {m['section']}"
    cite += "]"
    return f"{cite}\n{result['text']}"


def run_tool(name: str, inp: dict, collection, embed_client) -> str:
    """Execute one agent tool call and return a text result."""
    try:
        if name == "search_documents":
            where = {}
            if inp.get("card_id"):
                where["card_id"] = inp["card_id"]
            if inp.get("bank"):
                where["bank"] = inp["bank"]
            embedding = embed_text(embed_client, inp["query"])
            results = search_chunks(collection, embedding,
                                     k=inp.get("k", 6),
                                     where=where or None)
            if not results:
                return "No matching documents found."
            return "\n\n".join(format_search_result(r) for r in results)

        if name == "get_card":
            card_id = inp.get("card_id", "")
            bank = find_bank_for_card(card_id)
            if not bank:
                return f"Unknown card id: {card_id}"
            card = merge.find_record(merge.load_json_records(bank.cards_clean_path), card_id)
            pricing = merge.find_record(merge.load_json_records(bank.extracted_pricing_path), card_id)
            rewards = merge.find_record(merge.load_json_records(bank.extracted_rewards_path), card_id)
            return json.dumps({"card_info": card, "pricing": pricing, "rewards": rewards},
                              indent=1, ensure_ascii=False, default=str)

        if name == "get_pricing_field":
            field = inp.get("field", "")
            lines = []
            for key in sorted(BANKS):
                if inp.get("bank") and key != inp["bank"]:
                    continue
                bank = BANKS[key]
                if not bank.extracted_pricing_path.exists():
                    continue
                for r in merge.load_json_records(bank.extracted_pricing_path):
                    if field in r:
                        lines.append(f"{key} / {r.get('card_id')}: {r.get(field)}")
            if not lines:
                return f"Unknown field or no data: {field}"
            return "\n".join(lines)

        if name == "list_cards":
            out = []
            for key in sorted(BANKS):
                if inp.get("bank") and key != inp["bank"]:
                    continue
                bank = BANKS[key]
                if not bank.cards_clean_path.exists():
                    continue
                for c in merge.load_json_records(bank.cards_clean_path):
                    out.append(f"{key}: {c.get('card_id')} - {c.get('card_name')}")
            return "\n".join(out) or "No cards found."

        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {e}"


def converse_once(bedrock, messages, model_id):
    """One Bedrock converse call with retry."""
    for attempt in range(3):
        try:
            return bedrock.converse(
                modelId=model_id,
                system=[{"text": SYSTEM_PROMPT}],
                messages=messages,
                toolConfig=TOOL_CONFIG,
            )
        except ClientError as e:
            if attempt == 2:
                raise
            print(f"  (retrying after Bedrock error: {e})")


def chat(args):
    load_dotenv()
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    embed_client = get_embedding_client()

    single_bank = get_bank(args.bank) if args.bank else None
    collection = None
    preamble = None

    if args.card_id:
        bank = find_bank_for_card(args.card_id)
        if not bank:
            print(f"Unknown card id: {args.card_id}")
            sys.exit(1)
        docs = load_card_documents(bank, args.card_id)
        if not docs:
            print(f"No captured documents for {args.card_id}. Run the dumps first.")
            sys.exit(1)
        preamble = (f"Documents for card {args.card_id} "
                    f"({bank.display_name}). Answer questions about this card "
                    f"using these documents:\n\n{docs}")
        print(f"Card: {args.card_id} ({bank.display_name}), documents in context.")
    else:
        collection = get_collection()
        if collection.count() == 0:
            print("The document index is empty. Run: python src/rag/build_index.py")
            sys.exit(1)
        scope = f"bank '{args.bank}'" if args.bank else "all indexed banks"
        print(f"Retrieval mode over {scope} ({collection.count()} chunks indexed).")

    print("Ask a question about card terms. Type 'exit' to quit.\n")

    messages = []
    if preamble:
        messages.append({"role": "user", "content": [{"text": preamble}]})
        messages.append({"role": "assistant",
                         "content": [{"text": "Documents received. Ask me anything about this card's terms."}]})

    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            break

        messages.append({"role": "user", "content": [{"text": question}]})

        try:
            while True:
                resp = converse_once(bedrock, messages, args.model)
                message = resp["output"]["message"]
                messages.append(message)

                texts = [b["text"] for b in message["content"] if "text" in b]
                tool_uses = [b["toolUse"] for b in message["content"] if "toolUse" in b]

                if texts:
                    print("\nassistant> " + "\n".join(texts) + "\n")

                if not tool_uses:
                    break

                tool_results = []
                for tu in tool_uses:
                    args_str = json.dumps(tu["input"])[:100]
                    print(f"  -> {tu['name']}({args_str})")
                    result = run_tool(tu["name"], tu["input"], collection, embed_client)
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tu["toolUseId"],
                            "content": [{"text": result}],
                        }
                    })
                messages.append({"role": "user", "content": tool_results})
        except ClientError as e:
            print(f"\nBedrock error: {e}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Agentic chat over card terms and conditions")
    parser.add_argument("--card-id", default=None, help="Chat about one card (documents go in context, no index needed)")
    parser.add_argument("--bank", default=None, help="Retrieval mode over one bank (requires the index)")
    parser.add_argument("--model", default=MODEL_ID, help=f"Bedrock model id (default: {MODEL_ID})")
    args = parser.parse_args()
    chat(args)


if __name__ == "__main__":
    main()
