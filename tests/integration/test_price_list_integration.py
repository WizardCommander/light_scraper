"""Integration tests for price list integration in Lodes scraper."""

import pytest

from src.models import SKU
from src.scrapers.lodes_scraper import LodesScraper


class TestPriceListIntegration:
    """Integration tests for price list integration."""

    def setup_method(self):
        """Setup test fixture."""
        self.scraper = LodesScraper()

    def test_find_matching_price_list_product_returns_kelly_small_dome(self):
        """Should return Kelly small dome 50 when variant header contains 'small dome 50'."""
        variants = [
            {"Kelly small dome 50": "Bianco Opaco – 9010"},
            {"Kelly small dome 50": "Nero Opaco – 9005"},
        ]

        product, sku = self.scraper._find_matching_price_list_product(SKU("kelly"), variants)

        assert product is not None
        # JSON data (14126) matches because product_name contains "small dome 50"
        assert product["base_sku"] == "14126"
        assert product["product_name"] == "Kelly small dome 50"
        assert sku == "14126"

    def test_find_matching_price_list_product_returns_kelly_medium_dome(self):
        """Should return Kelly medium dome 60 when variant header contains 'medium dome 60'."""
        variants = [
            {"Kelly medium dome 60": "Bianco Opaco – 9010"},
        ]

        product, sku = self.scraper._find_matching_price_list_product(SKU("kelly"), variants)

        assert product is not None
        assert product["base_sku"] == "14127"
        assert product["product_name"] == "Kelly medium dome 60"
        assert sku == "14127"

    def test_find_matching_price_list_product_returns_kelly_large_dome(self):
        """Should return Kelly large dome 80 when variant header contains 'large dome 80'."""
        variants = [
            {"Kelly large dome 80": "Bianco Opaco – 9010"},
        ]

        product, sku = self.scraper._find_matching_price_list_product(SKU("kelly"), variants)

        assert product is not None
        assert product["base_sku"] == "14128"
        assert product["product_name"] == "Kelly large dome 80"
        assert sku == "14128"

    def test_find_matching_price_list_product_returns_first_when_no_size_match(self):
        """Should return first product when no specific size match found."""
        variants = [
            {"Color": "Bianco Opaco – 9010"},
        ]

        product, sku = self.scraper._find_matching_price_list_product(SKU("kelly"), variants)

        assert product is not None
        # First product matching 'kelly' in ALL_PRODUCTS
        assert product["base_sku"] == "14126"
        assert sku == "14126"

    def test_find_matching_price_list_product_returns_none_for_unknown_slug(self):
        """Should return None for unknown product slug."""
        variants = [{"Color": "White"}]

        product, sku = self.scraper._find_matching_price_list_product(
            SKU("unknown-product"), variants
        )

        assert product is None
        assert sku == "unknown-product"  # Returns original slug

    def test_enrich_attributes_adds_light_source(self):
        """Should add light source from price list to attributes."""
        price_list_product = {
            "light_source": "E27 LED B / L max 12cm\n3× 25 W",
            "dimmability": "TRIAC",
            "voltage": "220-240V",
        }
        attributes = {"Designer": "Andrea Tosetto"}

        enriched_attrs, _ = self.scraper._enrich_attributes_with_price_list(
            attributes, "", price_list_product
        )

        assert enriched_attrs["Light source"] == "E27 LED B / L max 12cm\n3× 25 W"
        assert enriched_attrs["Dimmbarkeit"] == "TRIAC"
        assert enriched_attrs["Voltage"] == "220-240V"
        assert enriched_attrs["Designer"] == "Andrea Tosetto"  # Preserves existing

    def test_enrich_attributes_adds_cable_length(self):
        """Should add cable length from price list."""
        price_list_product = {"cable_length": "max 250cm"}
        attributes = {}

        _, cable_length = self.scraper._enrich_attributes_with_price_list(
            attributes, "", price_list_product
        )

        assert cable_length == "max 250cm"

    def test_enrich_attributes_preserves_existing_cable_length(self):
        """Should not override existing cable length."""
        price_list_product = {"cable_length": "max 250cm"}
        attributes = {}

        _, cable_length = self.scraper._enrich_attributes_with_price_list(
            attributes, "max 300cm", price_list_product
        )

        assert cable_length == "max 300cm"  # Original preserved

    def test_enrich_attributes_returns_unchanged_when_no_price_list(self):
        """Should return unchanged attributes when no price list product."""
        attributes = {"Designer": "Andrea Tosetto"}

        enriched_attrs, cable_length = self.scraper._enrich_attributes_with_price_list(
            attributes, "max 300cm", None
        )

        assert enriched_attrs == attributes
        assert cable_length == "max 300cm"

    def test_map_variant_returns_sku_and_price_for_white(self):
        """Should map white color variant to SKU and price."""
        price_list_product = {
            "variants": [
                {
                    "sku": "14126 1000",
                    "color_code": "1000",
                    "price_eur": 572.00,
                }
            ]
        }
        variant = {"Kelly small dome 50": "Bianco Opaco – 9010"}

        sku, price = self.scraper._map_variant_to_price_list(variant, price_list_product)

        assert sku == "14126 1000"
        assert price == 572.00

    def test_map_variant_returns_sku_and_price_for_black(self):
        """Should map black color variant to SKU and price."""
        price_list_product = {
            "variants": [
                {
                    "sku": "14126 2000",
                    "color_code": "2000",
                    "price_eur": 572.00,
                }
            ]
        }
        variant = {"Kelly small dome 50": "Nero Opaco – 9005"}

        sku, price = self.scraper._map_variant_to_price_list(variant, price_list_product)

        assert sku == "14126 2000"
        assert price == 572.00

    def test_map_variant_returns_sku_and_price_for_bronze(self):
        """Should map bronze color variant to SKU and price."""
        price_list_product = {
            "variants": [
                {
                    "sku": "14126 3500",
                    "color_code": "3500",
                    "price_eur": 607.00,
                }
            ]
        }
        variant = {"Kelly small dome 50": "Bronzo Ramato"}

        sku, price = self.scraper._map_variant_to_price_list(variant, price_list_product)

        assert sku == "14126 3500"
        assert price == 607.00

    def test_map_variant_returns_none_when_no_color_match(self):
        """Should return None when color not found in price list."""
        price_list_product = {
            "variants": [
                {
                    "sku": "14126 1000",
                    "color_code": "1000",
                    "price_eur": 572.00,
                }
            ]
        }
        variant = {"Kelly small dome 50": "Unknown Color"}

        sku, price = self.scraper._map_variant_to_price_list(variant, price_list_product)

        assert sku is None
        assert price is None

    def test_map_variant_returns_none_when_no_price_list(self):
        """Should return None when no price list product provided."""
        variant = {"Kelly small dome 50": "Bianco Opaco – 9010"}

        sku, price = self.scraper._map_variant_to_price_list(variant, None)

        assert sku is None
        assert price is None
