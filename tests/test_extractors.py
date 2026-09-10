"""Tests for data extraction functions."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper.clean_data import (
    classify_reward_currency,
    extract_base_earn_rate,
    extract_sign_up_bonus,
    generate_card_id,
)


def test_disney_rewards_are_not_classified_as_cash_back():
    text = "Earn 1% in Disney Rewards Dollars on all card purchases."
    assert classify_reward_currency(text) == "Disney Rewards Dollars"
    assert extract_base_earn_rate(text) == 1.0


def test_disney_streaming_rate_is_not_a_base_rate():
    assert extract_base_earn_rate("Earn 10% in Disney Rewards Dollars at DisneyPlus.com") is None


def test_freedom_flex():
    """Freedom Flex should return 1.0 for base rate, not 5.0 category rate."""
    text = "Earn 5% cash back on up to $1,500 on combined purchases in bonus categories each quarter you activate. Plus, earn 5% cash back on travel purchased through Chase Travel, 3% on dining and drugstores, and 1% on all other purchases."
    assert extract_base_earn_rate(text) == 1.0


def test_freedom_unlimited():
    """Freedom Unlimited should return 1.5 for unlimited rate."""
    text = "unlimited 1.5% cash back or more on all purchases"
    assert extract_base_earn_rate(text) == 1.5


def test_disney_inspire():
    """Disney Inspire should return 1.0 for base rate, not 10.0 category rate."""
    text = "Earn 10% in Disney Rewards Dollars on purchases made directly at DisneyPlus.com... and 1% on all other card purchases"
    assert extract_base_earn_rate(text) == 1.0


def test_prime_visa():
    """Prime Visa should return 1.0 for base rate, not 5.0 Amazon rate."""
    text = "Earn unlimited 5% back at Amazon.com... and unlimited 1% back on all other purchases"
    assert extract_base_earn_rate(text) == 1.0


def test_pnc_cash_rewards_base_rate():
    """PNC Cash Rewards should return 1.0 for the all-other rate, not 4.0 gas."""
    text = "Earn 4% cash back on gas station purchases, 3% on dining purchases at restaurants, and 2% on grocery store purchases for the first $8,000 in combined purchases in these categories annually. Earn 1% cash back on all other purchases."
    assert extract_base_earn_rate(text) == 1.0


def test_pnc_cash_unlimited_base_rate():
    """PNC Cash Unlimited flat-rate copy should return 2.0."""
    text = "Earn unlimited 2% cash back on purchases"
    assert extract_base_earn_rate(text) == 2.0


def test_pnc_sign_up_bonus():
    """PNC phrasing 'making $1,000 in purchases' should parse."""
    text = "Earn a $200 bonus after opening an account and making $1,000 in purchases within the first 3 months"
    assert extract_sign_up_bonus(text) == (200, 1000, 3)


def test_pnc_card_id():
    """PNC product URLs should produce clean slugs, no .html or path prefixes."""
    url = "https://www.pnc.com/en/personal-banking/banking/credit-cards/pnc-cash-rewards-visa-credit-card.html"
    card_id = generate_card_id(url)
    assert card_id.startswith("pnc-cash-rewards-visa-credit-card-")
    assert ".html" not in card_id
    assert "personal-banking" not in card_id
    assert len(card_id.rsplit("-", 1)[1]) == 6


def test_chase_card_id_unchanged():
    """Chase URL id generation must not change."""
    url = "https://creditcards.chase.com/cash-back-credit-cards/freedom/flex?iCELL=6ZYD"
    assert generate_card_id(url) == "freedom-flex-a6950e"


if __name__ == '__main__':
    test_freedom_flex()
    print("✓ test_freedom_flex passed")
    
    test_freedom_unlimited()
    print("✓ test_freedom_unlimited passed")
    
    test_disney_inspire()
    print("✓ test_disney_inspire passed")
    
    test_prime_visa()
    print("✓ test_prime_visa passed")
    
    print("\n✓ All tests passed!")
