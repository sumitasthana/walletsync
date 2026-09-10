"""Tests for card image fetching and normalization."""

import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image

from src.images.fetch_card_images import (
    TARGET_SIZE,
    extract_card_image_url,
    normalize_image,
)


def _img_bytes(size, color, fmt):
    img = Image.new("RGB", size, color)
    out = BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


def test_normalize_landscape_png():
    result = normalize_image(_img_bytes((800, 500), (200, 30, 30), "PNG"))
    img = Image.open(BytesIO(result))
    assert img.format == "PNG"
    assert img.size == TARGET_SIZE


def test_normalize_portrait_jpeg():
    result = normalize_image(_img_bytes((300, 600), (30, 200, 30), "JPEG"))
    img = Image.open(BytesIO(result))
    assert img.format == "PNG"
    assert img.size == TARGET_SIZE


def test_normalize_identity_size():
    result = normalize_image(_img_bytes(TARGET_SIZE, (10, 10, 200), "PNG"))
    img = Image.open(BytesIO(result))
    assert img.size == TARGET_SIZE


def test_extract_prefers_card_art_path():
    html = """
    <html><body>
    <img alt="CHASE logo" src="/content/dam/logos/chasebank-logo.svg">
    <img alt="Chase Freedom Unlimited (Registered Trademark) credit card."
         src="/content/dam/jpmc-marketplace/card-art/freedom_unlimited_card_alt.png">
    </body></html>
    """
    url = extract_card_image_url(html, "https://creditcards.chase.com/x",
                                 "Chase Freedom Unlimited")
    assert url == ("https://creditcards.chase.com/content/dam/jpmc-marketplace/"
                   "card-art/freedom_unlimited_card_alt.png")


def test_extract_alt_fallback():
    html = """
    <html><head>
    <meta property="og:image" content="https://example.com/og.png">
    </head><body>
    <img alt="Slate (Service Mark) credit card." src="/img/slate.png">
    </body></html>
    """
    url = extract_card_image_url(html, "https://example.com/p", "Slate")
    assert url == "https://example.com/img/slate.png"


def test_extract_og_when_no_alt_match():
    html = """
    <html><head><meta property="og:image" content="/og.png"></head>
    <body></body></html>
    """
    url = extract_card_image_url(html, "https://example.com/p", "Some Card")
    assert url == "https://example.com/og.png"


def test_extract_skips_svg_without_fallback():
    html = '<html><body><img alt="Some Card Name credit card" src="/x.svg"></body></html>'
    url = extract_card_image_url(html, "https://example.com/p", "Some Card Name")
    assert url is None
