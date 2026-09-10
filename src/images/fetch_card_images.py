"""Fetch and normalize card images for a bank.

For each card, visits its product page, finds the card image, downloads it,
and stores a normalized PNG (640x400, contain-fit on transparent padding)
at data/<bank>/images/<card_id>.png, with the source URL recorded in
data/<bank>/images/manifest.json.

Usage:
    python src/images/fetch_card_images.py --bank chase
    python src/images/fetch_card_images.py --bank chase --limit 3
    python src/images/fetch_card_images.py --bank chase --force

For banks whose site is bot-blocked (PNC), save raw images named
<card_id>.<ext> into a folder and normalize them without network access:

    python src/images/fetch_card_images.py --bank pnc --normalize-dir <folder>
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.banks import get_bank
from src.scraper.clean_data import generate_card_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

TARGET_SIZE = (640, 400)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def normalize_image(data: bytes) -> bytes:
    """Convert image bytes to a PNG of TARGET_SIZE.

    The source is contain-fitted (aspect preserved) onto a transparent
    canvas, so every card image ends up the same size and form.
    """
    from PIL import Image

    img = Image.open(BytesIO(data))
    img = img.convert("RGBA")
    img.thumbnail(TARGET_SIZE, Image.LANCZOS)
    canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
    x = (TARGET_SIZE[0] - img.width) // 2
    y = (TARGET_SIZE[1] - img.height) // 2
    canvas.paste(img, (x, y), img)
    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def _alt_matches(alt: str, card_name: str) -> bool:
    """Check whether an img alt text plausibly names this card."""
    words = [w for w in card_name.replace("®", " ").replace("™", " ").split()
             if len(w) > 2]
    if not words:
        return False
    alt_lower = alt.lower()
    return any(w.lower() in alt_lower for w in words[:4])


def extract_card_image_url(html: str, page_url: str, card_name: str):
    """Find the card art image URL on a product page.

    Preference order: DAM card-art paths, an img whose alt names the card
    and says 'credit card', then the og:image meta tag. SVGs are skipped
    because they cannot be normalized.
    """
    soup = BeautifulSoup(html, "html.parser")

    def usable(src):
        return bool(src) and not src.lower().endswith(".svg")

    alt_matches = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        alt = (img.get("alt") or "").strip()
        if not src:
            continue
        if "/card-art/" in src and usable(src):
            return urljoin(page_url, src)
        if alt and len(alt) <= 90 and usable(src):
            if "credit card" in alt.lower() and _alt_matches(alt, card_name):
                alt_matches.append(src)

    if alt_matches:
        return urljoin(page_url, alt_matches[0])

    og = soup.find("meta", property="og:image")
    if og and og.get("content") and usable(og["content"]):
        return urljoin(page_url, og["content"])
    return None


def load_card_items(bank):
    """Unique cards from the raw manifest: (card_id, card_name, details_url)."""
    raw_cards = json.loads(bank.cards_raw_path.read_text(encoding="utf-8"))
    seen = set()
    items = []
    for card in raw_cards:
        url = card.get("details_url")
        if not url or url in seen:
            continue
        seen.add(url)
        items.append((generate_card_id(url), card.get("card_name", ""), url))
    return items


def save_image(out_dir: Path, card_id: str, png_bytes: bytes, source_url: str, manifest: dict):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{card_id}.png").write_bytes(png_bytes)
    manifest[card_id] = {
        "source_url": source_url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }


def normalize_dir(bank, folder: str):
    """Normalize manually captured images named <card_id>.<ext> into the bank's images dir."""
    out_dir = bank.data_dir / "images"
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    known = {card_id for card_id, _, _ in load_card_items(bank)}

    count = 0
    for path in sorted(Path(folder).iterdir()):
        card_id = path.stem
        if card_id not in known:
            log.warning(f"Skipping {path.name}: no card with id {card_id}")
            continue
        try:
            png_bytes = normalize_image(path.read_bytes())
        except Exception as e:
            log.error(f"Failed to normalize {path.name}: {e}")
            continue
        save_image(out_dir, card_id, png_bytes, f"manual:{path.name}", manifest)
        count += 1
        log.info(f"Normalized {card_id}")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Normalized {count} images into {out_dir}")


def fetch_bank(bank, limit=None, force=False):
    """Visit each product page, grab the card image, normalize, and save."""
    items = load_card_items(bank)
    if limit:
        items = items[:limit]

    out_dir = bank.data_dir / "images"
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    ok = fail = skip = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
        )
        page = context.new_page()

        for idx, (card_id, card_name, url) in enumerate(items, 1):
            dest = out_dir / f"{card_id}.png"
            if dest.exists() and not force:
                skip += 1
                continue

            log.info(f"[{idx}/{len(items)}] {card_name}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1500)
                img_url = extract_card_image_url(page.content(), url, card_name)
                if not img_url:
                    log.warning("  No image found on product page")
                    fail += 1
                    continue
                resp = requests.get(img_url, headers={"User-Agent": USER_AGENT}, timeout=30)
                if not resp.ok or not resp.content:
                    log.warning(f"  Download failed: HTTP {resp.status_code}")
                    fail += 1
                    continue
                save_image(out_dir, card_id, normalize_image(resp.content), img_url, manifest)
                ok += 1
                log.info(f"  Saved {card_id}.png from {img_url}")
            except Exception as e:
                log.error(f"  Failed: {e}")
                fail += 1

        browser.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Done: {ok} fetched, {skip} skipped (existing), {fail} failed. Output: {out_dir}")
    return fail


def main():
    parser = argparse.ArgumentParser(description="Fetch and normalize card images")
    parser.add_argument("--bank", required=True, help="Bank key (see src/banks/)")
    parser.add_argument("--limit", type=int, help="Limit number of cards (for debugging)")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if the image exists")
    parser.add_argument("--normalize-dir", default=None,
                        help="Normalize manually captured images named <card_id>.<ext> from this folder (no network)")
    args = parser.parse_args()

    bank = get_bank(args.bank)

    if args.normalize_dir:
        normalize_dir(bank, args.normalize_dir)
        return

    fetch_bank(bank, limit=args.limit, force=args.force)


if __name__ == "__main__":
    main()
