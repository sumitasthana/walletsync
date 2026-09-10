"""Chunk raw card documents for retrieval.

Builds retrieval chunks from three sources per bank:
- pricing dumps: one chunk per Schumer Box row, plus chunks over the full
  pricing page text
- rewards dumps: chunks over the rewards agreement text
- raw card manifests: one marketing chunk per unique card
"""

import json
from typing import List

from src.banks import BankConfig
from src.common.dump_utils import parse_frontmatter
from src.scraper.clean_data import generate_card_id

CHUNK_TARGET_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150


def chunk_text(text: str, target: int = CHUNK_TARGET_CHARS,
               overlap: int = CHUNK_OVERLAP_CHARS) -> List[str]:
    """Split whitespace-normalized text into overlapping chunks.

    The tail of a long document merges into the previous chunk when it is
    shorter than half the target size, so tiny fragments are avoided.
    """
    text = " ".join(text.split())
    n = len(text)
    if not text:
        return []
    if n <= target:
        return [text]

    chunks = []
    step = max(target - overlap, 1)
    start = 0
    while start < n:
        piece = text[start:start + target]
        if start + target >= n and chunks and len(piece) < target // 2:
            chunks[-1] = chunks[-1] + " " + piece
        else:
            chunks.append(piece)
        start += step
    return chunks


def _chunk_record(bank_key: str, card_id: str, card_name: str, doc_type: str,
                  text: str, section: str, source_url: str, idx: int) -> dict:
    return {
        "id": f"{bank_key}:{card_id}:{doc_type}:{idx:04d}",
        "text": text,
        "metadata": {
            "bank": bank_key,
            "card_id": card_id,
            "card_name": card_name,
            "doc_type": doc_type,
            "section": section or "",
            "source_url": source_url or "",
        },
    }


def _marketing_chunks(bank: BankConfig) -> List[dict]:
    """One chunk per unique card from the raw manifest's marketing copy."""
    if not bank.cards_raw_path.exists():
        return []
    raw_cards = json.loads(bank.cards_raw_path.read_text(encoding="utf-8"))
    chunks = []
    seen_urls = set()
    for card in raw_cards:
        url = card.get("details_url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        parts = []
        for field in ("annual_fee", "apr_info", "offer_headline",
                      "offer_threshold", "earning_rates", "marketing_tag"):
            value = card.get(field)
            if value:
                parts.append(f"{field.replace('_', ' ')}: {value}")
        if not parts:
            continue
        text = f"{card.get('card_name', '')}. " + " ".join(parts)
        chunks.append(_chunk_record(bank.key, generate_card_id(url),
                                    card.get("card_name", ""), "marketing",
                                    text, "marketing", url, 0))
    return chunks


def iter_bank_chunks(bank: BankConfig) -> List[dict]:
    """Build all retrieval chunks for one bank."""
    chunks = []

    for path in sorted(bank.raw_pricing_dir.glob("*.json")):
        try:
            dump = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        card_id = dump.get("card_id", "")
        card_name = dump.get("card_name", "")
        url = dump.get("pricing_terms_url", "")
        rows = dump.get("schumer_rows", {}) or {}
        for i, (label, value) in enumerate(rows.items()):
            chunks.append(_chunk_record(bank.key, card_id, card_name,
                                        "schumer_box", f"{label}: {value}",
                                        label, url, i))
        for i, text in enumerate(chunk_text(dump.get("full_page_text", ""))):
            chunks.append(_chunk_record(bank.key, card_id, card_name,
                                        "pricing_text", text, "", url, i))

    for path in sorted(bank.raw_rewards_dir.glob("*.txt")):
        frontmatter, body = parse_frontmatter(str(path))
        card_id = frontmatter.get("card_id", "")
        card_name = frontmatter.get("card_name", "")
        url = frontmatter.get("rewards_agreement_url", "")
        for i, text in enumerate(chunk_text(body)):
            chunks.append(_chunk_record(bank.key, card_id, card_name,
                                        "rewards_agreement", text, "", url, i))

    chunks.extend(_marketing_chunks(bank))
    return chunks
