"""Tests for the bank registry and configuration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.banks import BANKS, get_bank
from src.common.schemas import (
    ALLOWED_CATEGORIES,
    BASE_CATEGORIES,
    CHASE_CATEGORY_EXTENSIONS,
)


def test_registry_contains_chase_and_pnc():
    assert "chase" in BANKS
    assert "pnc" in BANKS


def test_chase_is_ready():
    assert BANKS["chase"].status == "ready"


def test_pnc_is_spike_only():
    assert BANKS["pnc"].status == "spike"


def test_get_bank_returns_config():
    chase = get_bank("chase")
    assert chase.key == "chase"
    assert chase.display_name == "Chase"


def test_get_bank_unknown_key_exits():
    try:
        get_bank("nope")
        assert False, "expected SystemExit for unknown bank"
    except SystemExit:
        pass


def test_chase_data_dir_exists():
    chase = BANKS["chase"]
    assert chase.cards_clean_path.exists()
    assert chase.raw_pricing_dir.exists()


def test_category_union_unchanged():
    expected = {
        "dining", "travel", "travel_chase_portal", "gas", "groceries",
        "drugstores", "streaming", "transit", "hotels", "airlines",
        "car_rental", "home_improvement", "rotating_5pct", "lyft",
        "peloton", "all_other", "other",
    }
    assert set(ALLOWED_CATEGORIES) == expected
    assert not set(CHASE_CATEGORY_EXTENSIONS) & set(BASE_CATEGORIES)
