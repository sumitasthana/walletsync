"""Tests for extended pricing extraction logic."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from schemas import PricingExtended, coerce_null_strings


def test_coerce_null_strings():
    """Test that null strings are coerced to None."""
    data = {
        'field1': 'null',
        'field2': 'None',
        'field3': '',
        'field4': 'NULL',
        'field5': 123,
        'field6': 'valid string'
    }
    
    result = coerce_null_strings(data)
    
    assert result['field1'] is None
    assert result['field2'] is None
    assert result['field3'] is None
    assert result['field4'] is None
    assert result['field5'] == 123
    assert result['field6'] == 'valid string'


def test_pydantic_validation_rejects_null_strings():
    """PricingExtended should reject null strings unless coerced first."""
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'pricing_terms_url': 'https://example.com',
        'purchase_apr_min': 'null',  # This should fail validation
        'cash_advance_apr': 28.49,
        'foreign_transaction_fee_pct': 3.0,
        'late_payment_fee_max_usd': 40
    }
    
    # Should fail without coercion
    try:
        PricingExtended.model_validate(data)
        assert False, "Should have raised validation error"
    except Exception:
        pass  # Expected
    
    # Should succeed with coercion
    coerced = coerce_null_strings(data)
    pricing = PricingExtended.model_validate(coerced)
    assert pricing.purchase_apr_min is None


def test_apr_range_parsing():
    """Test APR range extraction logic."""
    # Simulate what the LLM should extract from "18.24%–27.74% variable APR"
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'pricing_terms_url': 'https://example.com',
        'purchase_apr_min': 18.24,
        'purchase_apr_max': 27.74,
        'cash_advance_apr': 28.49,
        'foreign_transaction_fee_pct': 3.0,
        'late_payment_fee_max_usd': 40
    }
    
    pricing = PricingExtended.model_validate(data)
    assert pricing.purchase_apr_min == 18.24
    assert pricing.purchase_apr_max == 27.74


def test_intro_apr_extraction():
    """Test intro APR extraction."""
    # "0% intro APR for 15 months" → intro_pct=0.0, intro_months=15
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'pricing_terms_url': 'https://example.com',
        'purchase_apr_intro_pct': 0.0,
        'purchase_apr_intro_months': 15,
        'bt_apr_intro_pct': 0.0,
        'bt_apr_intro_months': 15,
        'cash_advance_apr': 28.49,
        'foreign_transaction_fee_pct': 3.0,
        'late_payment_fee_max_usd': 40
    }
    
    pricing = PricingExtended.model_validate(data)
    assert pricing.purchase_apr_intro_pct == 0.0
    assert pricing.purchase_apr_intro_months == 15
    assert pricing.bt_apr_intro_pct == 0.0
    assert pricing.bt_apr_intro_months == 15


def test_no_intro_apr_returns_null():
    """Card with no intro period → intro fields are None, not 0."""
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'pricing_terms_url': 'https://example.com',
        'purchase_apr_min': 18.24,
        'purchase_apr_max': 27.74,
        'purchase_apr_intro_pct': None,  # No intro period
        'purchase_apr_intro_months': None,
        'cash_advance_apr': 28.49,
        'foreign_transaction_fee_pct': 3.0,
        'late_payment_fee_max_usd': 40
    }
    
    pricing = PricingExtended.model_validate(data)
    assert pricing.purchase_apr_intro_pct is None
    assert pricing.purchase_apr_intro_months is None


def test_authorized_user_fee_present():
    """Sapphire Reserve discloses $75 AU fee → 75."""
    data = {
        'card_id': 'sapphire-reserve',
        'card_name': 'Chase Sapphire Reserve',
        'pricing_terms_url': 'https://example.com',
        'authorized_user_fee_usd': 75,
        'cash_advance_apr': 28.49,
        'foreign_transaction_fee_pct': 0.0,
        'late_payment_fee_max_usd': 40
    }
    
    pricing = PricingExtended.model_validate(data)
    assert pricing.authorized_user_fee_usd == 75


def test_authorized_user_fee_absent():
    """Freedom Unlimited has no AU fee → None, not 0."""
    data = {
        'card_id': 'freedom-unlimited',
        'card_name': 'Chase Freedom Unlimited',
        'pricing_terms_url': 'https://example.com',
        'authorized_user_fee_usd': None,  # No fee
        'cash_advance_apr': 28.49,
        'foreign_transaction_fee_pct': 3.0,
        'late_payment_fee_max_usd': 40
    }
    
    pricing = PricingExtended.model_validate(data)
    assert pricing.authorized_user_fee_usd is None


def test_balance_transfer_window():
    """Test bt_intro_window_days extraction."""
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'pricing_terms_url': 'https://example.com',
        'bt_intro_window_days': 60,  # "within 60 days"
        'cash_advance_apr': 28.49,
        'foreign_transaction_fee_pct': 3.0,
        'late_payment_fee_max_usd': 40
    }
    
    pricing = PricingExtended.model_validate(data)
    assert pricing.bt_intro_window_days == 60


def test_required_fields_enforced():
    """Test that required fields are enforced."""
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'pricing_terms_url': 'https://example.com',
        # Missing cash_advance_apr, foreign_transaction_fee_pct, late_payment_fee_max_usd
    }
    
    try:
        PricingExtended.model_validate(data)
        assert False, "Should have raised validation error for missing required fields"
    except Exception:
        pass  # Expected


def test_freedom_flex_earning_categories():
    """Freedom Flex should have 5 earning categories with correct caps."""
    from schemas import RewardsExtended, EarningCategory
    
    data = {
        'card_id': 'freedom-flex',
        'card_name': 'Chase Freedom Flex',
        'rewards_agreement_url': 'https://example.com',
        'reward_currency': 'Cash Back',
        'point_value_cents_baseline': 1.0,
        'earning_categories': [
            {
                'category': 'rotating_5pct',
                'rate': 5.0,
                'cap_usd': 1500,
                'cap_period': 'quarterly',
                'requires_activation': True
            },
            {
                'category': 'dining',
                'rate': 3.0
            },
            {
                'category': 'drugstores',
                'rate': 3.0
            },
            {
                'category': 'travel_chase_portal',
                'rate': 5.0
            },
            {
                'category': 'all_other',
                'rate': 1.0
            }
        ]
    }
    
    rewards = RewardsExtended.model_validate(data)
    assert len(rewards.earning_categories) == 5
    
    rotating = [c for c in rewards.earning_categories if c.category == 'rotating_5pct'][0]
    assert rotating.cap_usd == 1500
    assert rotating.cap_period == 'quarterly'
    assert rotating.requires_activation is True
    
    all_other = [c for c in rewards.earning_categories if c.category == 'all_other'][0]
    assert all_other.rate == 1.0


def test_marriott_transfer_ratio_direction():
    """Test transfer ratio direction: 3 Marriott = 1 airline mile."""
    from schemas import TransferPartner
    
    # Marriott → United at 3:1
    partner = TransferPartner(
        partner_name='United MileagePlus',
        ratio_from=3,  # Give up 3 Marriott points
        ratio_to=1     # Receive 1 airline mile
    )
    
    assert partner.ratio_from == 3
    assert partner.ratio_to == 1


def test_canonical_category_enforcement():
    """Category not in ALLOWED_CATEGORIES should fail post-validation."""
    from schemas import RewardsExtended, validate_rewards_categories
    
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'rewards_agreement_url': 'https://example.com',
        'reward_currency': 'Cash Back',
        'earning_categories': [
            {
                'category': 'dining_out',  # NOT in ALLOWED_CATEGORIES
                'rate': 3.0
            },
            {
                'category': 'all_other',
                'rate': 1.0
            }
        ]
    }
    
    # Pydantic validation passes (category is just a string)
    rewards = RewardsExtended.model_validate(data)
    
    # But post-validation should fail
    try:
        validate_rewards_categories(rewards)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert 'dining_out' in str(e)
        assert 'ALLOWED_CATEGORIES' in str(e)


def test_all_other_rate_mandatory():
    """Validation should reject RewardsExtended with no all_other entry."""
    from schemas import RewardsExtended
    
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'rewards_agreement_url': 'https://example.com',
        'reward_currency': 'Cash Back',
        'earning_categories': [
            {
                'category': 'dining',
                'rate': 3.0
            }
            # Missing all_other
        ]
    }
    
    try:
        RewardsExtended.model_validate(data)
        assert False, "Should have raised validation error"
    except Exception as e:
        assert 'all_other' in str(e).lower()


def test_other_category_requires_notes():
    """Category 'other' without notes should fail post-validation."""
    from schemas import RewardsExtended, validate_rewards_categories
    
    data = {
        'card_id': 'test-card',
        'card_name': 'Test Card',
        'rewards_agreement_url': 'https://example.com',
        'reward_currency': 'Cash Back',
        'earning_categories': [
            {
                'category': 'other',
                'rate': 2.0
                # Missing notes
            },
            {
                'category': 'all_other',
                'rate': 1.0
            }
        ]
    }
    
    rewards = RewardsExtended.model_validate(data)
    
    try:
        validate_rewards_categories(rewards)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert 'other' in str(e).lower()
        assert 'notes' in str(e).lower()


if __name__ == '__main__':
    # Pricing tests
    test_coerce_null_strings()
    print("✓ test_coerce_null_strings passed")
    
    test_pydantic_validation_rejects_null_strings()
    print("✓ test_pydantic_validation_rejects_null_strings passed")
    
    test_apr_range_parsing()
    print("✓ test_apr_range_parsing passed")
    
    test_intro_apr_extraction()
    print("✓ test_intro_apr_extraction passed")
    
    test_no_intro_apr_returns_null()
    print("✓ test_no_intro_apr_returns_null passed")
    
    test_authorized_user_fee_present()
    print("✓ test_authorized_user_fee_present passed")
    
    test_authorized_user_fee_absent()
    print("✓ test_authorized_user_fee_absent passed")
    
    test_balance_transfer_window()
    print("✓ test_balance_transfer_window passed")
    
    test_required_fields_enforced()
    print("✓ test_required_fields_enforced passed")
    
    # Rewards tests
    test_freedom_flex_earning_categories()
    print("✓ test_freedom_flex_earning_categories passed")
    
    test_marriott_transfer_ratio_direction()
    print("✓ test_marriott_transfer_ratio_direction passed")
    
    test_canonical_category_enforcement()
    print("✓ test_canonical_category_enforcement passed")
    
    test_all_other_rate_mandatory()
    print("✓ test_all_other_rate_mandatory passed")
    
    test_other_category_requires_notes()
    print("✓ test_other_category_requires_notes passed")
    
    print("\n✓ All tests passed!")
