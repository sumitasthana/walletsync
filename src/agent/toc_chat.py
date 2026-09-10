"""Agentic chat over card terms and conditions, powered by LangGraph.

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
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.agent.graph import MODEL_ID, build_agent
from src.agent.tools import find_bank_for_card, load_card_documents
from src.rag.embeddings import get_embedding_client
from src.rag.store import get_collection


def message_text(m) -> str:
    """Render a message's text content, handling content-block lists."""
    if isinstance(m.content, list):
        return "".join(p.get("text", "") for p in m.content if isinstance(p, dict))
    return str(m.content)


def chat(args):
    load_dotenv()

    collection = None
    embed_client = None
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
        embed_client = get_embedding_client()
        scope = f"bank '{args.bank}'" if args.bank else "all indexed banks"
        print(f"Retrieval mode over {scope} ({collection.count()} chunks indexed).")

    agent = build_agent(collection=collection, embed_client=embed_client,
                        model_id=args.model)

    print("Ask a question about card terms. Type 'exit' to quit.\n")

    history = []
    if preamble:
        history.append(HumanMessage(content=preamble))
        history.append(AIMessage(content="Documents received. Ask me anything about this card's terms."))

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

        input_messages = history + [HumanMessage(content=question)]
        try:
            result = agent.invoke({"messages": input_messages})
            history = result["messages"]

            for m in result["messages"][len(input_messages):]:
                for tc in getattr(m, "tool_calls", None) or []:
                    args_str = json.dumps(tc.get("args", {}))[:100]
                    print(f"  -> {tc.get('name')}({args_str})")

            for m in reversed(result["messages"]):
                if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
                    text = message_text(m)
                    if text:
                        print("\nassistant> " + text + "\n")
                    break
        except Exception as e:
            print(f"\nError: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Agentic chat over card terms and conditions (LangGraph)")
    parser.add_argument("--card-id", default=None, help="Chat about one card (documents go in context, no index needed)")
    parser.add_argument("--bank", default=None, help="Retrieval mode over one bank (requires the index)")
    parser.add_argument("--model", default=MODEL_ID, help=f"Bedrock model id (default: {MODEL_ID})")
    args = parser.parse_args()
    chat(args)


if __name__ == "__main__":
    main()
