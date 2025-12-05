"""Unit tests for Lodes price list module."""

import pytest

from src.lodes_price_list import (
    KELLY_PRODUCTS,
    get_all_product_colors,
    get_product_by_base_sku,
    get_product_by_slug,
    get_variant_price,
)


class TestGetProductBySlug:
    """Tests for get_product_by_slug function."""

    def test_returns_kelly_products_for_kelly_slug(self):
        """Should return all Kelly products when given 'kelly' slug."""
        products = get_product_by_slug("kelly")

        assert len(products) == 7
        assert all(p["url_slug"] == "kelly" for p in products)

    def test_returns_empty_list_for_unknown_slug(self):
        """Should return empty list for unknown slug."""
        products = get_product_by_slug("unknown-product")

        assert products == []

    def test_returns_products_with_correct_structure(self):
        """Should return products with all required fields."""
        products = get_product_by_slug("kelly")
        product = products[0]

        assert "base_sku" in product
        assert "product_name" in product
        assert "url_slug" in product
        assert "variants" in product
        assert "cable_length" in product
        assert "light_source" in product
        assert "dimmability" in product
        assert "voltage" in product
        assert "ip_rating" in product


class TestGetProductByBaseSku:
    """Tests for get_product_by_base_sku function."""

    def test_returns_kelly_small_dome_for_14126(self):
        """Should return Kelly small dome 50 for SKU 14126."""
        product = get_product_by_base_sku("14126")

        assert product is not None
        assert product["base_sku"] == "14126"
        assert product["product_name"] == "Kelly small dome 50"

    def test_returns_kelly_medium_dome_for_14127(self):
        """Should return Kelly medium dome 60 for SKU 14127."""
        product = get_product_by_base_sku("14127")

        assert product is not None
        assert product["base_sku"] == "14127"
        assert product["product_name"] == "Kelly medium dome 60"

    def test_returns_kelly_large_dome_for_14128(self):
        """Should return Kelly large dome 80 for SKU 14128."""
        product = get_product_by_base_sku("14128")

        assert product is not None
        assert product["base_sku"] == "14128"
        assert product["product_name"] == "Kelly large dome 80"

    def test_returns_none_for_unknown_sku(self):
        """Should return None for unknown SKU."""
        product = get_product_by_base_sku("99999")

        assert product is None


class TestGetVariantPrice:
    """Tests for get_variant_price function."""

    def test_returns_correct_price_for_kelly_small_white(self):
        """Should return 572.00 EUR for Kelly small dome white."""
        price = get_variant_price("14126 1000")

        assert price == 572.00

    def test_returns_correct_price_for_kelly_small_black(self):
        """Should return 572.00 EUR for Kelly small dome black."""
        price = get_variant_price("14126 2000")

        assert price == 572.00

    def test_returns_correct_price_for_kelly_small_bronze(self):
        """Should return 607.00 EUR for Kelly small dome bronze."""
        price = get_variant_price("14126 3500")

        assert price == 607.00

    def test_returns_correct_price_for_kelly_small_champagne(self):
        """Should return 607.00 EUR for Kelly small dome champagne."""
        price = get_variant_price("14126 4500")

        assert price == 607.00

    def test_returns_correct_price_for_kelly_medium_white(self):
        """Should return 883.00 EUR for Kelly medium dome white."""
        price = get_variant_price("14127 1000")

        assert price == 883.00

    def test_returns_correct_price_for_kelly_large_bronze(self):
        """Should return 1153.00 EUR for Kelly large dome bronze."""
        price = get_variant_price("14128 3500")

        assert price == 1153.00

    def test_returns_none_for_unknown_sku(self):
        """Should return None for unknown variant SKU."""
        price = get_variant_price("99999 1000")

        assert price is None

    def test_returns_none_for_sku_without_space(self):
        """Should return None for SKU without space separator."""
        price = get_variant_price("141261000")

        assert price is None

    def test_returns_none_for_unknown_color_code(self):
        """Should return None for valid base SKU but unknown color code."""
        price = get_variant_price("14126 9999")

        assert price is None


class TestGetAllProductColors:
    """Tests for get_all_product_colors function."""

    def test_returns_all_kelly_small_dome_colors(self):
        """Should return all color names for Kelly small dome."""
        product = get_product_by_base_sku("14126")
        colors = get_all_product_colors(product)

        assert colors == "Weiß Matt, Schwarz Matt, Bronze, Champagner Matt"

    def test_returns_all_kelly_medium_dome_colors(self):
        """Should return all color names for Kelly medium dome."""
        product = get_product_by_base_sku("14127")
        colors = get_all_product_colors(product)

        assert colors == "Weiß Matt, Schwarz Matt, Bronze, Champagner Matt"

    def test_returns_limited_colors_for_sphere_products(self):
        """Should return only available colors for sphere products (white and bronze only)."""
        product = get_product_by_base_sku("14122")  # Kelly small sphere
        colors = get_all_product_colors(product)

        assert colors == "Weiß Matt, Bronze"

    def test_returns_comma_separated_string(self):
        """Should return colors as comma-separated string."""
        product = get_product_by_base_sku("14126")
        colors = get_all_product_colors(product)

        assert isinstance(colors, str)
        assert ", " in colors


class TestPriceListData:
    """Tests for price list data structure integrity."""

    def test_all_kelly_products_have_required_fields(self):
        """Should have all required fields for every Kelly product."""
        required_fields = [
            "base_sku",
            "product_name",
            "url_slug",
            "variants",
            "cable_length",
            "light_source",
            "dimmability",
            "voltage",
            "ip_rating",
        ]

        for sku, product in KELLY_PRODUCTS.items():
            for field in required_fields:
                assert field in product, f"Product {sku} missing field: {field}"

    def test_all_variants_have_required_fields(self):
        """Should have all required fields for every variant."""
        required_fields = ["sku", "color_code", "color_name_en", "color_name_de", "price_eur"]

        for product in KELLY_PRODUCTS.values():
            for variant in product["variants"]:
                for field in required_fields:
                    assert field in variant, f"Variant missing field: {field}"

    def test_variant_skus_match_expected_format(self):
        """Should have variant SKUs in format 'XXXXX YYYY'."""
        for product in KELLY_PRODUCTS.values():
            for variant in product["variants"]:
                sku = variant["sku"]
                assert " " in sku, f"Variant SKU missing space: {sku}"
                parts = sku.split()
                assert len(parts) == 2, f"Variant SKU has wrong format: {sku}"
                assert len(parts[0]) == 5, f"Base SKU should be 5 digits: {sku}"
                assert parts[0].isdigit(), f"Base SKU should be numeric: {sku}"

    def test_all_prices_are_positive(self):
        """Should have positive prices for all variants."""
        for product in KELLY_PRODUCTS.values():
            for variant in product["variants"]:
                assert variant["price_eur"] > 0, f"Invalid price for {variant['sku']}"

    def test_dome_products_have_four_color_variants(self):
        """Should have 4 color variants for dome products."""
        dome_skus = ["14126", "14127", "14128"]
        for sku in dome_skus:
            product = KELLY_PRODUCTS[sku]
            assert len(product["variants"]) == 4, f"Dome product {sku} should have 4 variants"

    def test_sphere_products_have_two_color_variants(self):
        """Should have 2 color variants for sphere products."""
        sphere_skus = ["14122", "14123", "14124"]
        for sku in sphere_skus:
            product = KELLY_PRODUCTS[sku]
            assert len(product["variants"]) == 2, f"Sphere product {sku} should have 2 variants"

    def test_cluster_product_has_four_color_variants(self):
        """Should have 4 color variants for cluster product."""
        product = KELLY_PRODUCTS["14711"]
        assert len(product["variants"]) == 4
