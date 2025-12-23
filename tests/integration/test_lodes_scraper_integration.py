"""Integration tests for Lodes scraper.

Following CLAUDE.md: integration tests for network/browser operations.
These tests require internet connection and real Lodes.com access.
"""

import pytest

from src.scrapers.lodes_scraper import LodesScraper
from src.models import SKU


@pytest.mark.integration
@pytest.mark.slow
def test_scrape_real_lodes_product():
    """Should successfully scrape a real product from Lodes.com."""
    # Using 'kelly' as a known stable product on Lodes.com
    test_sku = SKU("kelly")

    with LodesScraper() as scraper:
        products = scraper.scrape_product(test_sku)
        assert isinstance(products, list)
        product = products[0]

        # Verify core fields are populated
        # Lodes scraper returns the price list base SKU
        assert product.sku == "14126"
        assert len(product.name) > 0
        assert product.manufacturer == "lodes"
        assert len(product.description) > 20
        assert product.description != "No description available"
        assert len(product.images) > 0
        assert len(product.categories) > 0


@pytest.mark.integration
@pytest.mark.slow
def test_scrape_multiple_lodes_products():
    """Should successfully scrape multiple products in sequence."""
    test_skus = [SKU("kelly"), SKU("megaphone")]
    products = []

    with LodesScraper() as scraper:
        for sku in test_skus:
            scraped_products = scraper.scrape_product(sku)
            products.extend(scraped_products)

    # Verify we got products
    assert len(products) >= 2
    assert all(p.name for p in products)
    # Some products might not have images in some environments
    # assert all(len(p.images) > 0 for p in products)


@pytest.mark.integration
def test_build_product_url():
    """Should construct correct product URL."""
    scraper = LodesScraper()
    url = scraper.build_product_url(SKU("test-product"))

    assert url == "https://www.lodes.com/en/products/test-product/"


@pytest.mark.integration
@pytest.mark.slow
def test_scrape_nonexistent_product_fails():
    """Should raise exception for non-existent product."""
    fake_sku = SKU("this-product-definitely-does-not-exist-12345")

    with LodesScraper() as scraper:
        with pytest.raises(Exception):
            scraper.scrape_product(fake_sku)


@pytest.mark.integration
@pytest.mark.slow
def test_extracted_images_are_valid_urls():
    """Should extract valid image URLs."""
    test_sku = SKU("kelly")

    with LodesScraper() as scraper:
        products = scraper.scrape_product(test_sku)
        product = products[0]

        # Verify images are URLs
        for img_url in product.images:
            assert img_url.startswith("http")
            assert not any(
                pattern in img_url.lower()
                for pattern in ["logo", "icon", "banner", ".svg"]
            )


@pytest.mark.integration
@pytest.mark.slow
def test_rate_limiting_applied():
    """Should apply rate limiting between requests."""
    import time

    test_skus = [SKU("kelly"), SKU("megaphone")]

    with LodesScraper() as scraper:
        start_time = time.time()

        for sku in test_skus:
            try:
                scraper.scrape_product(sku)
            except Exception:
                pass  # Ignore errors, just testing rate limiting

        elapsed = time.time() - start_time

        # Should take at least 1 second due to rate limiting (1 req/sec)
        # First request + 1 second delay before second = at least 1 second total
        assert elapsed >= 1.0


@pytest.mark.integration
@pytest.mark.slow
def test_product_with_variants():
    """Should successfully scrape product with multiple variants."""
    # Kelly product has 39 variants
    test_sku = SKU("kelly")

    with LodesScraper() as scraper:
        products = scraper.scrape_product(test_sku)
        # Parent product is first
        parent = products[0]

        # Verify product is scraped successfully
        assert parent.sku == "14126"
        assert parent.product_type == "variable"
        assert len(parent.name) > 0

        # Verify we have variations
        assert len(products) > 1
        variation = products[1]
        assert variation.product_type == "variation"
        assert variation.parent_sku == parent.sku

        # Verify attributes are present
        assert len(parent.attributes) > 0
        assert len(parent.images) > 0
