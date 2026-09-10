"""Tests for retrieval chunking, corpus building, and the vector store."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.banks import BANKS
from src.rag.corpus import chunk_text, iter_bank_chunks


def test_chunk_text_empty():
    assert chunk_text("   \n  ") == []


def test_chunk_text_short_stays_whole():
    assert chunk_text("hello world") == ["hello world"]


def test_chunk_text_long_splits_with_overlap():
    text = " ".join(f"w{i}" for i in range(2000))
    chunks = chunk_text(text, target=1000, overlap=100)
    assert len(chunks) >= 2
    # consecutive chunks overlap by design
    assert chunks[1][:50] in chunks[0]
    # tail merges instead of leaving a tiny fragment
    assert all(len(c) >= 100 for c in chunks)


def test_chunk_text_normalizes_whitespace():
    text = "line one\n\nline two\n   with   spaces"
    assert chunk_text(text) == ["line one line two with spaces"]


def test_corpus_chase_chunks():
    chunks = iter_bank_chunks(BANKS["chase"])
    assert len(chunks) > 300

    doc_types = {}
    for c in chunks:
        doc_types[c["metadata"]["doc_type"]] = doc_types.get(c["metadata"]["doc_type"], 0) + 1

    assert doc_types.get("schumer_box", 0) > 200
    assert doc_types.get("rewards_agreement", 0) > 50
    assert doc_types.get("marketing", 0) >= 35

    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids))
    for c in chunks:
        assert c["metadata"]["bank"] == "chase"
        assert c["metadata"]["card_id"]
        assert c["text"]


def test_corpus_pnc_marketing_only():
    chunks = iter_bank_chunks(BANKS["pnc"])
    marketing = [c for c in chunks if c["metadata"]["doc_type"] == "marketing"]
    assert len(marketing) == 4
    # no pricing or rewards documents captured yet for PNC
    others = [c for c in chunks if c["metadata"]["doc_type"] != "marketing"]
    assert others == []


def test_store_roundtrip(tmp_path):
    from src.rag.store import get_collection, search_chunks, upsert_chunks

    collection = get_collection(str(tmp_path / "idx"))
    meta = {"bank": "t", "card_id": "1", "card_name": "Card",
            "doc_type": "schumer_box", "section": "", "source_url": ""}
    chunks = [
        {"id": "t:1:a:0000", "text": "foreign transaction fee is three percent", "metadata": dict(meta)},
        {"id": "t:1:a:0001", "text": "late payment fee up to forty dollars", "metadata": dict(meta)},
    ]

    def embed(text):
        return [1.0, 0.0] if "foreign" in text else [0.0, 1.0]

    assert upsert_chunks(collection, chunks, embed) == 2

    def no_embed(text):
        raise AssertionError("unchanged chunks should not be re-embedded")

    assert upsert_chunks(collection, chunks, no_embed) == 0

    results = search_chunks(collection, [1.0, 0.0], k=1)
    assert "foreign" in results[0]["text"]
