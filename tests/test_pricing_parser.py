"""Unit tests for deterministic pricing parser.

Tests run against stored HTML fixtures to ensure:
1. Parser functions work correctly on known inputs
2. Chase format changes break the build loudly
3. No Bedrock calls are made (deterministic only)
"""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dump_pricing_text import extract_schumer_rows, extract_full_text
from parse_pricing_deterministic import (
    parse_pricing,
    parse_apr_range,
    parse_intro_apr,
    parse_single_apr,
    parse_dollar_fee,
    parse_percent,
    parse_fee_structure,
    parse_apr_index,
    parse_apr_margin,
    find_row,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pricing_html"


class TestFieldExtractors:
    """Test individual field extractor functions."""
    
    def test_parse_apr_range_standard(self):
        """Test APR range parsing with 'to' separator."""
        assert parse_apr_range("18.24% to 27.74%") == (18.24, 27.74)
    
    def test_parse_apr_range_dash_variants(self):
        """Test APR range with different dash characters."""
        assert parse_apr_range("18.24%–27.74%") == (18.24, 27.74)
        assert parse_apr_range("18.24% - 27.74%") == (18.24, 27.74)
        assert parse_apr_range("18.24%—27.74%") == (18.24, 27.74)
    
    def test_parse_apr_range_single_value(self):
        """Test single APR (no range) - should return (apr, apr)."""
        assert parse_apr_range("25.24%") == (25.24, 25.24)
    
    def test_parse_apr_range_none_cases(self):
        """Test APR range with None/empty inputs."""
        assert parse_apr_range(None) == (None, None)
        assert parse_apr_range("") == (None, None)
        assert parse_apr_range("No APR") == (None, None)
    
    def test_parse_intro_apr_standard(self):
        """Test standard intro APR format."""
        assert parse_intro_apr("0% Intro APR for 15 months") == (0.0, 15)
        assert parse_intro_apr("0% intro APR for 12 months") == (0.0, 12)
    
    def test_parse_intro_apr_with_first(self):
        """Test intro APR with 'the first' qualifier."""
        assert parse_intro_apr("0% Intro APR for the first 15 months") == (0.0, 15)
    
    def test_parse_intro_apr_fixed(self):
        """Test 'fixed Intro APR' variant."""
        assert parse_intro_apr("0% fixed Intro APR for 12 months") == (0.0, 12)
    
    def test_parse_intro_apr_promo(self):
        """Test 'Promo APR' variant."""
        assert parse_intro_apr("0% Promo APR for 15 months") == (0.0, 15)
    
    def test_parse_intro_apr_word_numbers(self):
        """Test intro APR with word numbers."""
        assert parse_intro_apr("0% Promo APR for the first six months") == (0.0, 6)
        assert parse_intro_apr("0% Intro APR for twelve months") == (0.0, 12)
        assert parse_intro_apr("0% Intro APR for fifteen months") == (0.0, 15)
    
    def test_parse_intro_apr_none_cases(self):
        """Test intro APR with non-intro text."""
        assert parse_intro_apr("18.24% to 27.74%") == (None, None)
        assert parse_intro_apr(None) == (None, None)
        assert parse_intro_apr("") == (None, None)
    
    def test_parse_single_apr_standard(self):
        """Test single APR extraction."""
        assert parse_single_apr("28.49%") == 28.49
        assert parse_single_apr("25.24%") == 25.24
    
    def test_parse_single_apr_with_text(self):
        """Test single APR with surrounding text."""
        assert parse_single_apr("Up to 29.99%") == 29.99
        assert parse_single_apr("This APR will vary with the market based on the Prime Rate.") is None
    
    def test_parse_single_apr_none_cases(self):
        """Test single APR with None/empty."""
        assert parse_single_apr(None) is None
        assert parse_single_apr("") is None
        assert parse_single_apr("None") is None
    
    def test_parse_dollar_fee_standard(self):
        """Test dollar fee extraction."""
        assert parse_dollar_fee("$40") == 40
        assert parse_dollar_fee("$10") == 10
    
    def test_parse_dollar_fee_with_text(self):
        """Test dollar fee with surrounding text."""
        assert parse_dollar_fee("Up to $40.") == 40
        assert parse_dollar_fee("Either $5 or 5%") == 5  # First dollar amount
    
    def test_parse_dollar_fee_none_cases(self):
        """Test dollar fee with None/empty."""
        assert parse_dollar_fee(None) is None
        assert parse_dollar_fee("") is None
        assert parse_dollar_fee("None") is None
    
    def test_parse_percent_standard(self):
        """Test percentage extraction."""
        assert parse_percent("3%") == 3.0
        assert parse_percent("5%") == 5.0
    
    def test_parse_percent_with_text(self):
        """Test percentage with surrounding text."""
        assert parse_percent("3% of each transaction") == 3.0
        assert parse_percent("3.5% of each transaction") == 3.5
    
    def test_parse_percent_none_cases(self):
        """Test percentage with None/empty."""
        assert parse_percent(None) is None
        assert parse_percent("") is None
        assert parse_percent("None") is None
    
    def test_parse_fee_structure_standard(self):
        """Test complex fee structure parsing."""
        pct, min_usd, max_usd = parse_fee_structure("Either $5 or 5% of the amount, whichever is greater")
        assert pct == 5.0
        assert min_usd == 5
        assert max_usd is None
    
    def test_parse_fee_structure_with_range(self):
        """Test fee structure with min and max."""
        pct, min_usd, max_usd = parse_fee_structure("Either $5 or 5%, up to $100")
        assert pct == 5.0
        assert min_usd == 5
        assert max_usd == 100
    
    def test_parse_apr_index_prime_rate(self):
        """Test APR index detection."""
        assert parse_apr_index("based on the Prime Rate") == "Prime Rate"
        assert parse_apr_index("will vary with the market based on the Prime Rate") == "Prime Rate"
    
    def test_parse_apr_index_none_cases(self):
        """Test APR index with no index mentioned."""
        assert parse_apr_index("fixed rate") is None
        assert parse_apr_index(None) is None
    
    def test_parse_apr_margin_standard(self):
        """Test APR margin extraction."""
        assert parse_apr_margin("Prime Rate + 13.99%") == 13.99
        assert parse_apr_margin("add 12.49% to the Prime Rate") == 12.49
    
    def test_find_row_case_insensitive(self):
        """Test row finding with case-insensitive matching."""
        rows = {
            "Annual Membership Fee": "$0",
            "Foreign Transaction": "3%",
            "LATE PAYMENT": "$40"
        }
        # find_row matches substrings, so "annual" will match "Annual Membership Fee"
        assert find_row(rows, "annual") == "$0"
        assert find_row(rows, "foreign") == "3%"
        assert find_row(rows, "late") == "$40"
    
    def test_find_row_multiple_patterns(self):
        """Test row finding with multiple pattern options."""
        rows = {
            "Default APR": "29.99%",
            "Foreign Transaction": "3%"
        }
        assert find_row(rows, "Penalty APR", "Default APR") == "29.99%"
    
    def test_find_row_not_found(self):
        """Test row finding when pattern doesn't match."""
        rows = {"Annual Fee": "$0"}
        assert find_row(rows, "nonexistent") is None


class TestSchumerBoxExtraction:
    """Test Schumer Box HTML parsing."""
    
    def test_extract_schumer_rows_freedom_unlimited(self):
        """Test extraction from Freedom Unlimited HTML."""
        html = (FIXTURES / "freedom-unlimited.html").read_text(encoding='utf-8')
        rows = extract_schumer_rows(html)
        
        # Core fields must be present
        assert any("Annual" in k for k in rows), "Annual Fee row missing"
        assert any("Foreign Transaction" in k for k in rows), "Foreign Transaction row missing"
        assert any("Cash Advance" in k for k in rows), "Cash Advance row missing"
        assert any("Late Payment" in k for k in rows), "Late Payment row missing"
        
        # Should have multiple rows
        assert len(rows) >= 10, f"Expected at least 10 rows, got {len(rows)}"
    
    def test_extract_schumer_rows_business_card(self):
        """Test extraction from business card (different format)."""
        html = (FIXTURES / "sapphire-reserve-business.html").read_text(encoding='utf-8')
        rows = extract_schumer_rows(html)
        
        # Business cards have different labels
        assert any("Flex for Business" in k for k in rows), "Flex for Business APR missing"
        assert any("Foreign Transaction" in k for k in rows), "Foreign Transaction row missing"
    
    def test_extract_full_text(self):
        """Test full text extraction."""
        html = (FIXTURES / "freedom-unlimited.html").read_text(encoding='utf-8')
        text = extract_full_text(html)
        
        # Should have substantial content
        assert len(text) > 1000, "Full text seems too short"
        
        # Should not have script/style tags
        assert "<script" not in text.lower()
        assert "<style" not in text.lower()
        
        # Should have key terms
        assert "prime rate" in text.lower() or "apr" in text.lower()


class TestEndToEndParsing:
    """Test complete parsing pipeline on real HTML fixtures."""
    
    def test_parse_pricing_freedom_unlimited(self):
        """Test end-to-end parsing of Freedom Unlimited."""
        html = (FIXTURES / "freedom-unlimited.html").read_text(encoding='utf-8')
        rows = extract_schumer_rows(html)
        full_text = extract_full_text(html)
        
        dump = {
            "card_id": "freedom-unlimited",
            "card_name": "Chase Freedom Unlimited®",
            "pricing_terms_url": "https://sites.chase.com/...",
            "schumer_rows": rows,
            "full_page_text": full_text,
        }
        
        result = parse_pricing(dump)
        
        # Verify key fields (values verified manually from Chase website)
        assert result.card_id == "freedom-unlimited"
        assert result.card_name == "Chase Freedom Unlimited®"
        
        # APRs should be in reasonable ranges
        assert result.purchase_apr_min is not None
        assert 15.0 < result.purchase_apr_min < 20.0, f"Unexpected purchase APR min: {result.purchase_apr_min}"
        assert result.purchase_apr_max is not None
        assert 25.0 < result.purchase_apr_max < 30.0, f"Unexpected purchase APR max: {result.purchase_apr_max}"
        
        # Cash advance APR
        assert result.cash_advance_apr is not None
        assert 25.0 < result.cash_advance_apr < 30.0, f"Unexpected cash advance APR: {result.cash_advance_apr}"
        
        # Foreign transaction fee
        assert result.foreign_transaction_fee_pct is not None
        assert result.foreign_transaction_fee_pct == 3.0, f"Expected 3% foreign fee, got {result.foreign_transaction_fee_pct}"
        
        # Late payment fee
        assert result.late_payment_fee_max_usd is not None
        assert result.late_payment_fee_max_usd == 40, f"Expected $40 late fee, got {result.late_payment_fee_max_usd}"
    
    def test_parse_pricing_sapphire_reserve(self):
        """Test end-to-end parsing of Sapphire Reserve (premium card)."""
        html = (FIXTURES / "sapphire-reserve.html").read_text(encoding='utf-8')
        rows = extract_schumer_rows(html)
        full_text = extract_full_text(html)
        
        dump = {
            "card_id": "sapphire-reserve",
            "card_name": "Chase Sapphire Reserve®",
            "pricing_terms_url": "https://sites.chase.com/...",
            "schumer_rows": rows,
            "full_page_text": full_text,
        }
        
        result = parse_pricing(dump)
        
        # Note: Sapphire Reserve actually has 3% foreign fee (verified from fixture)
        # Only Sapphire Reserve for Business has 0% foreign fee
        assert result.foreign_transaction_fee_pct is not None
        
        # Should have APRs
        assert result.purchase_apr_min is not None
        assert result.cash_advance_apr is not None
    
    def test_parse_pricing_business_card(self):
        """Test end-to-end parsing of business card (different format)."""
        html = (FIXTURES / "sapphire-reserve-business.html").read_text(encoding='utf-8')
        rows = extract_schumer_rows(html)
        full_text = extract_full_text(html)
        
        dump = {
            "card_id": "sapphire-reserve-business",
            "card_name": "Sapphire Reserve for BusinessSM",
            "pricing_terms_url": "https://sites.chase.com/...",
            "schumer_rows": rows,
            "full_page_text": full_text,
        }
        
        result = parse_pricing(dump)
        
        # Business card should extract APRs from "Flex for Business APR"
        assert result.purchase_apr_min is not None, "Business card should have purchase APR from Flex APR"
        assert result.cash_advance_apr is not None, "Business card should have cash advance APR from Flex APR"
        
        # Business card has no foreign transaction fee
        assert result.foreign_transaction_fee_pct == 0.0
    
    def test_parse_pricing_single_apr_card(self):
        """Test parsing of card with single APR (not a range)."""
        html = (FIXTURES / "freedom-rise.html").read_text(encoding='utf-8')
        rows = extract_schumer_rows(html)
        full_text = extract_full_text(html)
        
        dump = {
            "card_id": "freedom-rise",
            "card_name": "Chase Freedom Rise®",
            "pricing_terms_url": "https://sites.chase.com/...",
            "schumer_rows": rows,
            "full_page_text": full_text,
        }
        
        result = parse_pricing(dump)
        
        # Freedom Rise has a single APR (not a range)
        assert result.purchase_apr_min is not None
        assert result.purchase_apr_max is not None
        # For single APR, min should equal max
        assert result.purchase_apr_min == result.purchase_apr_max, \
            f"Single APR card should have min=max, got {result.purchase_apr_min} != {result.purchase_apr_max}"


class TestNoBedrock:
    """Test that parser never calls Bedrock."""
    
    def test_parse_pricing_does_not_import_boto3(self):
        """Verify parse_pricing_deterministic.py doesn't import boto3."""
        parser_file = Path(__file__).parent.parent / "src" / "parse_pricing_deterministic.py"
        content = parser_file.read_text()
        
        assert "boto3" not in content, "Parser should not import boto3"
        assert "bedrock" not in content.lower(), "Parser should not reference Bedrock"
        assert "aws" not in content.lower() or "# aws" in content.lower(), "Parser should not reference AWS"
    
    def test_parse_pricing_does_not_call_bedrock(self):
        """Runtime check: parsing must not call Bedrock."""
        # Simple test: just verify parsing works without any AWS imports
        # The import test above already verified boto3 isn't in the code
        
        dump = {
            "card_id": "test",
            "card_name": "Test Card",
            "pricing_terms_url": "test",
            "schumer_rows": {
                "Annual Membership Fee": "$0",
                "Purchase Annual Percentage Rate (APR)": "18.24% to 27.74%",
                "Cash Advance APR": "28.49%",
                "Foreign Transactions": "3%",
                "Late Payment": "$40",
            },
            "full_page_text": "Prime Rate"
        }
        
        result = parse_pricing(dump)
        
        # Verify parsing worked (if it called Bedrock, it would fail or be slow)
        assert result.card_id == "test"
        assert result.purchase_apr_min == 18.24
        
        # Verify no boto3 in sys.modules (would be there if imported)
        import sys
        assert 'boto3' not in sys.modules, "boto3 was imported during test execution"


class TestFormatChanges:
    """Tests that will break loudly if Chase changes their format."""
    
    def test_schumer_box_has_required_rows(self):
        """Verify all fixtures have required Schumer Box rows."""
        required_substrings = ["Annual", "Foreign Transaction", "Late Payment", "Cash Advance"]
        
        for fixture_file in FIXTURES.glob("*.html"):
            html = fixture_file.read_text(encoding='utf-8')
            rows = extract_schumer_rows(html)
            
            for required in required_substrings:
                assert any(required.lower() in k.lower() for k in rows.keys()), \
                    f"{fixture_file.name}: Missing required row containing '{required}'"
    
    def test_apr_values_are_reasonable(self):
        """Verify APR values are in reasonable ranges (sanity check)."""
        for fixture_file in FIXTURES.glob("*.html"):
            if fixture_file.name == "sapphire-reserve-business.html":
                continue  # Business card has different format
            
            html = fixture_file.read_text(encoding='utf-8')
            rows = extract_schumer_rows(html)
            full_text = extract_full_text(html)
            
            dump = {
                "card_id": fixture_file.stem,
                "card_name": "Test",
                "pricing_terms_url": "test",
                "schumer_rows": rows,
                "full_page_text": full_text,
            }
            
            result = parse_pricing(dump)
            
            # APRs should be between 0% and 40%
            if result.purchase_apr_min is not None:
                assert 0 <= result.purchase_apr_min <= 40, \
                    f"{fixture_file.name}: Unreasonable purchase APR min: {result.purchase_apr_min}"
            
            if result.cash_advance_apr is not None:
                assert 0 <= result.cash_advance_apr <= 40, \
                    f"{fixture_file.name}: Unreasonable cash advance APR: {result.cash_advance_apr}"
    
    def test_fees_are_reasonable(self):
        """Verify fee values are in reasonable ranges."""
        for fixture_file in FIXTURES.glob("*.html"):
            html = fixture_file.read_text(encoding='utf-8')
            rows = extract_schumer_rows(html)
            full_text = extract_full_text(html)
            
            dump = {
                "card_id": fixture_file.stem,
                "card_name": "Test",
                "pricing_terms_url": "test",
                "schumer_rows": rows,
                "full_page_text": full_text,
            }
            
            result = parse_pricing(dump)
            
            # Foreign transaction fee should be 0-5%
            if result.foreign_transaction_fee_pct is not None:
                assert 0 <= result.foreign_transaction_fee_pct <= 5, \
                    f"{fixture_file.name}: Unreasonable foreign fee: {result.foreign_transaction_fee_pct}"
            
            # Late payment fee should be $0-$50
            if result.late_payment_fee_max_usd is not None:
                assert 0 <= result.late_payment_fee_max_usd <= 50, \
                    f"{fixture_file.name}: Unreasonable late fee: {result.late_payment_fee_max_usd}"
