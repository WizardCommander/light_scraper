"""Unit tests for lodes_scraper.py pure functions."""

from src.scrapers.lodes_scraper import _is_numeric_sku


class TestIsNumericSku:
    """Tests for _is_numeric_sku function."""

    def test_returns_true_for_numeric_sku(self):
        """Should return True for SKU containing only digits."""
        result = _is_numeric_sku("14126")

        assert result is True

    def test_returns_true_for_single_digit(self):
        """Should return True for single digit SKU."""
        result = _is_numeric_sku("1")

        assert result is True

    def test_returns_true_for_large_numeric_sku(self):
        """Should return True for large numeric SKU."""
        result = _is_numeric_sku("123456789")

        assert result is True

    def test_returns_false_for_text_slug(self):
        """Should return False for text slug."""
        result = _is_numeric_sku("kelly")

        assert result is False

    def test_returns_false_for_alphanumeric_sku(self):
        """Should return False for mixed alphanumeric SKU."""
        result = _is_numeric_sku("14126abc")

        assert result is False

    def test_returns_false_for_sku_with_hyphen(self):
        """Should return False for SKU with hyphen."""
        result = _is_numeric_sku("14126-1")

        assert result is False

    def test_returns_true_for_sku_with_space(self):
        """Should return True for SKU with space (base SKU + color code)."""
        result = _is_numeric_sku("14126 1000")

        assert result is True

    def test_returns_false_for_empty_string(self):
        """Should return False for empty string."""
        result = _is_numeric_sku("")

        assert result is False

    def test_returns_false_for_sku_with_leading_zeros(self):
        """Should still work with leading zeros (valid numeric)."""
        result = _is_numeric_sku("00123")

        assert result is True

    def test_returns_false_for_sku_with_special_characters(self):
        """Should return False for SKU with special characters."""
        result = _is_numeric_sku("14126!")

        assert result is False

    def test_returns_false_for_sku_with_underscore(self):
        """Should return False for SKU with underscore."""
        result = _is_numeric_sku("14126_1")

        assert result is False

    def test_returns_false_for_sku_starting_with_number(self):
        """Should return False if starts with number but has letters."""
        result = _is_numeric_sku("14126-abc")

        assert result is False
