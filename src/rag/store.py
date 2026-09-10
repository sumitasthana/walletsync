"""ChromaDB vector store for card document chunks."""

from pathlib import Path
from typing import List, Optional

import chromadb

INDEX_DIR = "data/vector_index"
COLLECTION_NAME = "card_documents"
BATCH_SIZE = 32


def get_collection(index_dir: str = INDEX_DIR):
    """Open (or create) the persistent document collection."""
    Path(index_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=index_dir)
    return client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(collection, chunks: List[dict], embed_fn, force: bool = False) -> int:
    """Insert or update chunks, skipping chunks whose text is unchanged.

    Returns the number of chunks (re)embedded.
    """
    if not force:
        existing = {}
        ids = [c["id"] for c in chunks]
        for i in range(0, len(ids), 100):
            got = collection.get(ids=ids[i:i + 100])
            existing.update(zip(got["ids"], got["documents"]))
        chunks = [c for c in chunks if existing.get(c["id"]) != c["text"]]

    count = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        collection.upsert(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
            embeddings=[embed_fn(c["text"]) for c in batch],
        )
        count += len(batch)
    return count


def search_chunks(collection, query_embedding, k: int = 6,
                  where: Optional[dict] = None) -> List[dict]:
    """Return the top chunks for a query embedding."""
    res = collection.query(query_embeddings=[query_embedding],
                           n_results=k, where=where)
    results = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0],
                               res["distances"][0]):
        results.append({"text": text, "metadata": meta, "distance": dist})
    return results
