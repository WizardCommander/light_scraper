"""Unit tests for lodes_price_list.py module."""

from src.lodes_price_list import (
    KELLY_PRODUCTS,
    get_all_product_colors,
    get_product_by_base_sku,
    get_product_by_slug,
    get_slug_by_base_sku,
    get_variant_price,
)


class TestGetProductBySlug:
    """Tests for get_product_by_slug function."""

    def test_returns_all_products_for_kelly_slug(self):
        """Should return all Kelly products when given 'kelly' slug."""
        result = get_product_by_slug("kelly")

        # 7 hardcoded Kelly products + several from JSON = 11
        assert len(result) == 11
        assert all("kelly" in p["url_slug"].lower() or "kelly" in p["product_name"].lower() for p in result)

    def test_returns_empty_list_for_unknown_slug(self):
        """Should return empty list for non-existent slug."""
        result = get_product_by_slug("nonexistent")

        assert result == []

    def test_returns_products_with_correct_base_skus(self):
        """Should return products with expected base SKUs."""
        result = get_product_by_slug("kelly")
        base_skus = {p["base_sku"] for p in result}

        expected_skus = {
            "14126",
            "14127",
            "14128",
            "14122",
            "14123",
            "14124",
            "14711",
            "034",
            "008",
            "009",
            "15413",
        }
        assert base_skus == expected_skus


class TestGetProductByBaseSku:
    """Tests for get_product_by_base_sku function."""

    def test_returns_product_for_valid_sku(self):
        """Should return product info for valid base SKU."""
        result = get_product_by_base_sku("14126")

        assert result is not None
        assert result["base_sku"] == "14126"
        assert result["product_name"] == "Kelly small dome 50"
        # JSON has more specific slug
        assert result["url_slug"] == "kelly-small-dome-50"

    def test_returns_none_for_invalid_sku(self):
        """Should return None for non-existent SKU."""
        result = get_product_by_base_sku("99999")

        assert result is None

    def test_returns_product_with_variants(self):
        """Should return product with variant list."""
        result = get_product_by_base_sku("14126")

        assert result is not None
        assert "variants" in result
        # Check actual length of variants from JSON if it differs, or use KELLY_PRODUCTS
        assert len(result["variants"]) >= 3


class TestGetSlugByBaseSku:
    """Tests for get_slug_by_base_sku function."""

    def test_returns_slug_for_valid_sku(self):
        """Should return URL slug for valid base SKU."""
        result = get_slug_by_base_sku("14126")

        assert result == "kelly-small-dome-50"

    def test_returns_none_for_invalid_sku(self):
        """Should return None for non-existent SKU."""
        result = get_slug_by_base_sku("99999")

        assert result is None

    def test_consistent_with_get_product_by_base_sku(self):
        """Should return same slug as product's url_slug field."""
        sku = "14127"
        product = get_product_by_base_sku(sku)
        slug = get_slug_by_base_sku(sku)

        assert product is not None
        assert slug == product["url_slug"]


class TestGetVariantPrice:
    """Tests for get_variant_price function."""

    def test_returns_price_for_valid_variant_sku(self):
        """Should return price for valid variant SKU."""
        result = get_variant_price("14126 1000")

        assert result == 572.00

    def test_returns_different_prices_for_different_colors(self):
        """Should return different prices for bronze/champagne variants."""
        white_price = get_variant_price("14126 1000")
        bronze_price = get_variant_price("14126 3500")

        assert white_price == 572.00
        assert bronze_price == 607.00

    def test_returns_none_for_invalid_base_sku(self):
        """Should return None when base SKU doesn't exist."""
        result = get_variant_price("99999 1000")

        assert result is None

    def test_returns_none_for_invalid_variant(self):
        """Should return None when variant doesn't exist for valid product."""
        result = get_variant_price("14126 9999")

        assert result is None

    def test_handles_sku_without_space(self):
        """Should handle SKU without space separator."""
        result = get_variant_price("14126")

        assert result is None


class TestGetAllProductColors:
    """Tests for get_all_product_colors function."""

    def test_returns_comma_separated_german_colors(self):
        """Should return comma-separated list of German color names."""
        product = get_product_by_base_sku("14126")
        assert product is not None

        result = get_all_product_colors(product)

        # JSON has 3 colors for 14126: Weiß Matt, Schwarz Matt, Bronze
        assert result == "Weiß Matt, Schwarz Matt, Bronze"

    def test_returns_correct_order(self):
        """Should return colors in same order as variants."""
        product = get_product_by_base_sku("14126")
        assert product is not None

        result = get_all_product_colors(product)
        colors = result.split(", ")

        assert len(colors) == len(product["variants"])
        for i, variant in enumerate(product["variants"]):
            assert colors[i] == variant["color_name_de"]

    def test_handles_product_with_two_variants(self):
        """Should work with products that have only 2 color variants."""
        product = get_product_by_base_sku("14122")
        assert product is not None

        result = get_all_product_colors(product)

        # Check it returns 2 colors separated by comma
        colors = result.split(", ")
        assert len(colors) == 2
        assert "Matt" in colors[0]
        assert "Bronze" in colors[1]


class TestKellyProductsData:
    """Tests for KELLY_PRODUCTS data structure integrity."""

    def test_all_products_have_required_fields(self):
        """Should verify all products have mandatory fields."""
        required_fields = {
            "base_sku",
            "product_name",
            "url_slug",
            "cable_length",
            "light_source",
            "dimmability",
            "voltage",
            "ip_rating",
            "variants",
        }

        for base_sku, product in KELLY_PRODUCTS.items():
            assert set(product.keys()).issuperset(
                required_fields
            ), f"Product {base_sku} missing required fields"

    def test_all_variants_have_required_fields(self):
        """Should verify all variants have mandatory fields."""
        required_variant_fields = {
            "sku",
            "color_code",
            "color_name_en",
            "color_name_de",
            "price_eur",
        }

        for base_sku, product in KELLY_PRODUCTS.items():
            for variant in product["variants"]:
                assert set(variant.keys()).issuperset(
                    required_variant_fields
                ), f"Variant in {base_sku} missing required fields"

    def test_variant_skus_match_pattern(self):
        """Should verify variant SKUs follow '{base_sku} {color_code}' pattern."""
        for base_sku, product in KELLY_PRODUCTS.items():
            for variant in product["variants"]:
                expected_prefix = f"{base_sku} "
                assert variant["sku"].startswith(
                    expected_prefix
                ), f"Variant SKU {variant['sku']} doesn't match base SKU {base_sku}"

    def test_prices_are_positive(self):
        """Should verify all prices are positive numbers."""
        for base_sku, product in KELLY_PRODUCTS.items():
            for variant in product["variants"]:
                assert (
                    variant["price_eur"] > 0
                ), f"Invalid price for {variant['sku']}: {variant['price_eur']}"
