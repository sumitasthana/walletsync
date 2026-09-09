"""Tests for data extraction functions."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper.clean_data import extract_base_earn_rate


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
