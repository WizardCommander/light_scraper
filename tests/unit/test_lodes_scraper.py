"""Unit tests for Lodes scraper helper functions.

Following CLAUDE.md: parameterized inputs, test entire structure, no trivial asserts.
"""

import pytest

from src.types import SKU
from src.scrapers.lodes_scraper import LodesScraper


@pytest.mark.unit
class TestExtractSkuFromUrl:
    """Test SKU extraction from product URLs."""

    @pytest.mark.parametrize(
        "url,expected_sku",
        [
            ("/en/products/kelly/", "kelly"),
            ("https://www.lodes.com/en/products/kelly/", "kelly"),
            ("/en/products/a-tube-suspension/", "a-tube-suspension"),
            ("https://www.lodes.com/en/products/megaphone", "megaphone"),
            ("/products/nostalgia/", "nostalgia"),
        ],
    )
    def test_extract_sku_from_valid_urls(self, url: str, expected_sku: str):
        """Test SKU extraction from various valid URL formats."""
        scraper = LodesScraper()
        result = scraper._extract_sku_from_url(url)

        assert result is not None
        assert result == SKU(expected_sku)

    @pytest.mark.parametrize(
        "url",
        [
            "/en/collections/",
            "https://www.lodes.com/en/",
            "/about-us/",
            "invalid-url",
            "",
        ],
    )
    def test_extract_sku_from_invalid_urls(self, url: str):
        """Test SKU extraction returns None for invalid URLs."""
        scraper = LodesScraper()
        result = scraper._extract_sku_from_url(url)

        assert result is None


@pytest.mark.unit
def test_build_product_url():
    """Test product URL construction from SKU."""
    scraper = LodesScraper()
    sku = SKU("kelly")

    url = scraper.build_product_url(sku)

    assert url == "https://www.lodes.com/en/products/kelly/"
    assert "/products/" in url
    assert url.startswith("https://")


@pytest.mark.unit
class TestIsValidUrl:
    """Test URL validation helper function."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.example.com/image.jpg",
            "http://example.com/image.png",
            "https://cdn.lodes.com/products/kelly/image1.jpg",
            "//www.example.com/image.jpg",  # Protocol-relative URL
            "  https://example.com/image.jpg  ",  # With whitespace
            "HTTPS://EXAMPLE.COM/IMAGE.JPG",  # Uppercase
        ],
    )
    def test_valid_urls(self, url: str):
        """Test validation accepts valid URLs."""
        scraper = LodesScraper()
        result = scraper._is_valid_url(url)

        assert result is True

    @pytest.mark.parametrize(
        "url",
        [
            "",  # Empty string
            "   ",  # Whitespace only
            "not-a-url",  # No protocol
            "www.example.com/image.jpg",  # No protocol
            "/relative/path/image.jpg",  # Relative path
            "ftp://example.com/file.jpg",  # Wrong protocol
        ],
    )
    def test_invalid_urls(self, url: str):
        """Test validation rejects invalid URLs."""
        scraper = LodesScraper()
        result = scraper._is_valid_url(url)

        assert result is False
