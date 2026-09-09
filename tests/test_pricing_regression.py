"""Regression tests: deterministic parser vs LLM baseline."""

import json
from pathlib import Path
import pytest

# Load baseline and current outputs
BASELINE = json.load(open("data/baseline_pricing_llm.json", encoding='utf-8'))
CURRENT = json.load(open("data/extracted_pricing_extended.json", encoding='utf-8'))


def _by_card_id(records):
    """Convert list of records to dict keyed by card_id."""
    return {r["card_id"]: r for r in records}


BASELINE_MAP = _by_card_id(BASELINE)
CURRENT_MAP = _by_card_id(CURRENT)

# Fields to compare. Divergences here are either regressions or improvements.
COMPARE_FIELDS = [
    "purchase_apr_min",
    "purchase_apr_max",
    "purchase_apr_intro_pct",
    "purchase_apr_intro_months",
    "bt_apr_min",
    "bt_apr_max",
    "bt_apr_intro_pct",
    "bt_apr_intro_months",
    "bt_intro_window_days",
    "cash_advance_apr",
    "penalty_apr_max",
    "foreign_transaction_fee_pct",
    "balance_transfer_fee_pct",
    "balance_transfer_fee_min_usd",
    "balance_transfer_fee_max_usd",
    "cash_advance_fee_pct",
    "cash_advance_fee_min_usd",
    "late_payment_fee_max_usd",
    "authorized_user_fee_usd",
    "apr_index",
    "purchase_apr_margin",
]


@pytest.mark.parametrize("card_id", sorted(BASELINE_MAP.keys()))
def test_no_regression(card_id):
    """
    Test that deterministic parser matches or improves on LLM baseline.
    
    Regressions: LLM had value, deterministic returned None
    Divergences: Both non-null but different values (may be LLM error)
    Improvements: Deterministic has value, LLM had None
    """
    baseline = BASELINE_MAP[card_id]
    current = CURRENT_MAP.get(card_id)
    
    assert current, f"{card_id} missing from deterministic output"
    
    regressions = []
    divergences = []
    improvements = []
    
    for field in COMPARE_FIELDS:
        b_val = baseline.get(field)
        c_val = current.get(field)
        
        # Regression: LLM had value, deterministic None
        if b_val is not None and c_val is None:
            regressions.append(f"{field}: LLM had {b_val!r}, deterministic returned None")
        
        # Divergence: Both non-null but different
        elif b_val is not None and c_val is not None and b_val != c_val:
            # For numeric fields, check if close enough (within 0.01)
            if isinstance(b_val, (int, float)) and isinstance(c_val, (int, float)):
                if abs(b_val - c_val) > 0.01:
                    divergences.append(f"{field}: LLM={b_val!r} deterministic={c_val!r}")
            else:
                divergences.append(f"{field}: LLM={b_val!r} deterministic={c_val!r}")
        
        # Improvement: Deterministic has value, LLM None
        elif b_val is None and c_val is not None:
            improvements.append(f"{field}: deterministic={c_val!r} (LLM had None)")
    
    # Print divergences for manual review (may be LLM hallucinations)
    if divergences:
        print(f"\n{card_id} DIVERGENCES (manual review needed):")
        for d in divergences:
            print(f"  - {d}")
    
    # Print improvements
    if improvements:
        print(f"\n{card_id} IMPROVEMENTS:")
        for i in improvements:
            print(f"  + {i}")
    
    # Fail on regressions
    if regressions:
        msg = f"{card_id} REGRESSIONS:\n" + "\n".join(f"  - {r}" for r in regressions)
        pytest.fail(msg)


def test_new_card_extracted():
    """Test that Sapphire Reserve for Business is now extracted (was failed in LLM run)."""
    # This card failed in LLM extraction, should succeed in deterministic
    srb_id = "sapphire-reserve-5a3e5c"
    
    # Should be in current output
    assert srb_id in CURRENT_MAP, "Sapphire Reserve for Business missing from deterministic output"
    
    srb = CURRENT_MAP[srb_id]
    
    # Should have key fields
    assert srb["card_name"] == "Sapphire Reserve for BusinessSM"
    assert srb["cash_advance_apr"] is not None, "cash_advance_apr should be extracted"
    assert srb["foreign_transaction_fee_pct"] is not None, "foreign_transaction_fee_pct should be extracted"
    assert srb["late_payment_fee_max_usd"] is not None, "late_payment_fee_max_usd should be extracted"
    
    print(f"\n✓ Sapphire Reserve for Business successfully extracted:")
    print(f"  Purchase APR: {srb['purchase_apr_min']} - {srb['purchase_apr_max']}")
    print(f"  Cash Advance APR: {srb['cash_advance_apr']}")
    print(f"  Foreign Transaction Fee: {srb['foreign_transaction_fee_pct']}%")
    print(f"  Late Payment Fee: ${srb['late_payment_fee_max_usd']}")


def test_total_coverage():
    """Test that deterministic parser covers all baseline cards plus the failed one."""
    baseline_count = len(BASELINE_MAP)
    current_count = len(CURRENT_MAP)
    
    # Should have at least as many cards as baseline
    assert current_count >= baseline_count, \
        f"Deterministic output has fewer cards ({current_count}) than baseline ({baseline_count})"
    
    # Should have exactly 41 cards (40 baseline + 1 previously failed)
    assert current_count == 41, f"Expected 41 cards, got {current_count}"
    
    print(f"\n✓ Coverage: {current_count}/41 cards (100%)")
    print(f"  Baseline (LLM): {baseline_count}/41 (98%)")
    print(f"  Deterministic: {current_count}/41 (100%)")
    print(f"  Improvement: +{current_count - baseline_count} card")
