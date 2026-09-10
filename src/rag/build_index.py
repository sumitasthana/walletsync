"""Build the document vector index.

Embeds Schumer Box rows, full pricing page text, rewards agreement text,
and marketing copy for every bank with raw data.

Usage:
    python src/rag/build_index.py            # all banks with data
    python src/rag/build_index.py --bank chase
    python src/rag/build_index.py --force    # re-embed everything
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.banks import BANKS
from src.rag.corpus import iter_bank_chunks
from src.rag.embeddings import embed_text, get_embedding_client
from src.rag.store import get_collection, upsert_chunks


def main():
    parser = argparse.ArgumentParser(description="Build the card document vector index")
    parser.add_argument("--bank", default=None, help="Only index this bank (default: all with data)")
    parser.add_argument("--force", action="store_true", help="Re-embed all chunks")
    args = parser.parse_args()

    client = get_embedding_client()
    collection = get_collection()

    total_new = 0
    for key in sorted(BANKS):
        bank = BANKS[key]
        if args.bank and bank.key != args.bank:
            continue
        chunks = iter_bank_chunks(bank)
        if not chunks:
            print(f"{bank.key}: no documents to index, skipping")
            continue
        n_new = upsert_chunks(collection, chunks,
                              lambda t: embed_text(client, t),
                              force=args.force)
        total_new += n_new
        print(f"{bank.key}: {len(chunks)} chunks total, {n_new} (re)embedded")

    print(f"Done. {total_new} chunks (re)embedded. Index: data/vector_index/")


if __name__ == "__main__":
    main()
