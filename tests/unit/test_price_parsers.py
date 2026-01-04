"""Unit tests for price list parsers."""

import pytest

from scripts.parsers.pdf_parser_base import (
    extract_price_eur,
    validate_price,
    validate_sku,
)


class TestPriceExtraction:
    """Tests for EUR price extraction."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("572,00 €", 572.00),
            ("€ 572,00", 572.00),
            ("572.00 €", 572.00),
            ("1240,00", 1240.00),
            ("€1240.00", 1240.00),
            ("3264,00 €", 3264.00),
            ("no price here", None),
            ("abc,de", None),
        ],
    )
    def test_extract_price_eur(self, text, expected):
        """Test EUR price extraction from various formats."""
        result = extract_price_eur(text)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected)


class TestPriceValidation:
    """Tests for price validation."""

    @pytest.mark.parametrize(
        "price,expected",
        [
            (100.0, True),
            (572.0, True),
            (99999.0, True),
            (0.0, False),
            (-10.0, False),
            (100000.0, False),
            (None, False),
        ],
    )
    def test_validate_price(self, price, expected):
        """Test price validation logic."""
        assert validate_price(price) == expected


class TestSKUValidation:
    """Tests for SKU validation."""

    @pytest.mark.parametrize(
        "sku,pattern,expected",
        [
            ("14126 1000", r"^\d{5}\s+\d{4}$", True),
            ("14126 2000", r"^\d{5}\s+\d{4}$", True),
            ("14126", r"^\d{5}\s+\d{4}$", False),
            ("1412 1000", r"^\d{5}\s+\d{4}$", False),
            ("0162/1", r"^\d{4}/[A-Z0-9]+$", True),
            ("0162/Z", r"^\d{4}/[A-Z0-9]+$", True),
            ("0162/BY", r"^\d{4}/[A-Z0-9]+$", True),
            ("162/1", r"^\d{4}/[A-Z0-9]+$", False),
        ],
    )
    def test_validate_sku(self, sku, pattern, expected):
        """Test SKU validation against patterns."""
        assert validate_sku(sku, pattern) == expected


class TestLodesParsing:
    """Tests for Lodes-specific parsing logic."""

    def test_lodes_sku_pattern(self):
        """Test Lodes SKU pattern matching."""
        from scripts.parsers.lodes_pdf_parser import LodesTableParser

        import re

        pattern = LodesTableParser.SKU_PATTERN
        test_cases = [
            ("14126 1000", True),
            ("14127 2000", True),
            ("14128 3500", True),
            ("1412 1000", False),  # Too few digits in base
            ("14126 100", False),  # Too few digits in color code
        ]

        for sku, should_match in test_cases:
            match = re.search(pattern, sku)
            assert (match is not None) == should_match


class TestVibiaParsing:
    """Tests for Vibia-specific parsing logic."""

    def test_vibia_simple_sku_pattern(self):
        """Test Vibia simple SKU pattern matching."""
        from scripts.parsers.vibia_pdf_parser import VibiaTableParser

        import re

        pattern = VibiaTableParser.SIMPLE_SKU_PATTERN
        test_cases = [
            ("0162/1", True),
            ("0162/Z", True),
            ("0162/BY", True),
            ("162/1", False),  # Too few digits in base
            ("0162-1", False),  # Wrong separator
        ]

        for sku, should_match in test_cases:
            match = re.search(pattern, sku)
            assert (match is not None) == should_match
