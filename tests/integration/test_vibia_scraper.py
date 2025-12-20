"""Integration tests for Vibia scraper.

Following CLAUDE.md best practices:
- Tests verify real scraping behavior
- Use actual Vibia website (may be slow)
- Test critical user workflows
"""

import pytest
from src.scrapers.vibia_scraper import VibiaScraper
from src.models import SKU


@pytest.mark.slow
class TestVibiaScraper:
    """Integration tests for VibiaScraper."""

    @pytest.fixture
    def scraper(self):
        """Create scraper instance for testing."""
        return VibiaScraper()

    def test_build_product_url_from_model(self, scraper):
        model = "0162"
        url = scraper.build_product_url(SKU(model), language="de")
        assert (
            url
            == "https://www.vibia.com/de/int/kollektionen/pendelleuchten-circus-pendelleuchte"
        )

    def test_build_product_url_from_slug(self, scraper):
        slug = "circus"
        url = scraper.build_product_url(SKU(slug), language="de")
        assert (
            url
            == "https://www.vibia.com/de/int/kollektionen/pendelleuchten-circus-pendelleuchte"
        )

    def test_build_product_url_english(self, scraper):
        model = "0162"
        url = scraper.build_product_url(SKU(model), language="en")
        assert (
            url
            == "https://www.vibia.com/en/int/kollektionen/pendelleuchten-circus-pendelleuchte"
        )

    def test_extract_slug_from_numeric_sku(self, scraper):
        sku = SKU("0162")
        slug = scraper._extract_slug_from_sku(sku)
        assert slug == "circus"

    def test_extract_slug_from_simplified_sku(self, scraper):
        sku = SKU("0162/1")
        slug = scraper._extract_slug_from_sku(sku)
        assert slug == "circus"

    def test_extract_slug_from_slug(self, scraper):
        sku = SKU("circus")
        slug = scraper._extract_slug_from_sku(sku)
        assert slug == "circus"

    def test_get_base_sku_from_model(self, scraper):
        sku = SKU("0162")
        base_sku = scraper._get_base_sku(sku)
        assert base_sku == "0162"

    def test_get_base_sku_from_simplified(self, scraper):
        sku = SKU("0162/1")
        base_sku = scraper._get_base_sku(sku)
        assert base_sku == "0162"

    def test_get_base_sku_from_slug(self, scraper):
        sku = SKU("circus")
        base_sku = scraper._get_base_sku(sku)
        assert base_sku == "0162"  # First product in Circus family


@pytest.mark.slow
@pytest.mark.live
class TestVibiaLiveScraping:
    """Live scraping tests against actual Vibia website.

    These tests are marked as 'live' and may be slow or flaky.
    They verify that the scraper works with real website data.
    """

    @pytest.fixture
    def scraper(self):
        """Create scraper instance with browser."""
        scraper = VibiaScraper()
        scraper.setup_browser(headless=True)
        yield scraper
        scraper.teardown_browser()

    @pytest.mark.skipif(
        True,
        reason="Live scraping test - enable manually to verify against real website",
    )
    def test_scrape_circus_product(self, scraper):
        """Test scraping actual Circus product from Vibia website."""
        sku = SKU("circus")
        products = scraper.scrape_product(sku)

        # Verify we got products back
        assert len(products) > 0

        # Verify parent product
        parent = products[0]
        assert parent.product_type == "variable"
        assert "Circus" in parent.name
        assert len(parent.images) > 0
        assert parent.manufacturer == "vibia"

        # Verify we have variants
        variants = [p for p in products if p.product_type == "variation"]
        assert len(variants) > 0

        # Verify variant structure
        for variant in variants:
            assert variant.parent_sku is not None
            assert variant.regular_price is not None
            assert variant.regular_price > 0
            assert variant.variation_attributes is not None
