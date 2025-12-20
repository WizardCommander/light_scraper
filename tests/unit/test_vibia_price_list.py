"""Unit tests for Vibia price list module.

Following CLAUDE.md best practices:
- Tests use descriptive names stating what they verify
- Parameterized inputs rather than literals
- Test edge cases and realistic input
- Strong assertions over weak ones
"""

import pytest
from src import vibia_price_list


class TestGetProductByModel:
    """Tests for get_product_by_model function."""

    def test_returns_product_for_valid_model(self):
        model = "0162"
        result = vibia_price_list.get_product_by_model(model)
        assert result is not None
        assert result["base_sku"] == model
        assert result["product_name"] == "Circus Pendelleuchte Ø 20 cm"

    def test_returns_none_for_invalid_model(self):
        invalid_model = "9999"
        result = vibia_price_list.get_product_by_model(invalid_model)
        assert result is None

    def test_returns_none_for_empty_model(self):
        result = vibia_price_list.get_product_by_model("")
        assert result is None


class TestGetProductBySlug:
    """Tests for get_product_by_slug function."""

    def test_returns_all_products_with_matching_slug(self):
        slug = "circus"
        results = vibia_price_list.get_product_by_slug(slug)
        assert len(results) == 3  # 0162, 0167, 0164
        assert all(p["url_slug"] == slug for p in results)

    def test_returns_empty_list_for_invalid_slug(self):
        invalid_slug = "nonexistent"
        results = vibia_price_list.get_product_by_slug(invalid_slug)
        assert results == []

    def test_returns_correct_models_for_circus(self):
        slug = "circus"
        results = vibia_price_list.get_product_by_slug(slug)
        models = {p["base_sku"] for p in results}
        assert models == {"0162", "0167", "0164"}


class TestGetVariantPrice:
    """Tests for get_variant_price function."""

    def test_returns_correct_price_for_valid_sku(self):
        sku = "0162/1"
        expected_price = 350.00
        result = vibia_price_list.get_variant_price(sku)
        assert result == expected_price

    def test_returns_none_for_invalid_sku(self):
        invalid_sku = "9999/1"
        result = vibia_price_list.get_variant_price(invalid_sku)
        assert result is None

    def test_returns_none_for_invalid_variant(self):
        invalid_variant = "0162/X"
        result = vibia_price_list.get_variant_price(invalid_variant)
        assert result is None

    def test_returns_different_prices_for_different_variants(self):
        sku1 = "0162/1"
        sku2 = "0162/Y"
        price1 = vibia_price_list.get_variant_price(sku1)
        price2 = vibia_price_list.get_variant_price(sku2)
        assert price1 != price2
        assert price1 == 350.00
        assert price2 == 455.00


class TestGetAllVariants:
    """Tests for get_all_variants function."""

    def test_returns_all_variants_for_product(self):
        product = vibia_price_list.get_product_by_model("0162")
        assert product is not None
        variants = vibia_price_list.get_all_variants(product)
        assert len(variants) == 6

    def test_each_variant_has_required_fields(self):
        product = vibia_price_list.get_product_by_model("0162")
        assert product is not None
        variants = vibia_price_list.get_all_variants(product)
        for variant in variants:
            assert "sku" in variant
            assert "price_eur" in variant
            assert "surface_name_en" in variant
            assert "led_name_en" in variant
            assert "control_name_en" in variant

    def test_variant_prices_are_positive(self):
        product = vibia_price_list.get_product_by_model("0162")
        assert product is not None
        variants = vibia_price_list.get_all_variants(product)
        assert all(v["price_eur"] > 0 for v in variants)


class TestGetCategoryForSlug:
    """Tests for get_category_for_slug function."""

    def test_returns_correct_category_for_circus(self):
        slug = "circus"
        result = vibia_price_list.get_category_for_slug(slug)
        assert result == "pendelleuchten"

    def test_returns_none_for_invalid_slug(self):
        invalid_slug = "nonexistent"
        result = vibia_price_list.get_category_for_slug(invalid_slug)
        assert result is None


class TestParseSkuComponents:
    """Tests for parse_sku_components function."""

    def test_parses_full_sku_format(self):
        full_sku = "1160 10 / 1A _ 18"
        result = vibia_price_list.parse_sku_components(full_sku)
        assert result is not None
        assert result["model"] == "1160"
        assert result["surface"] == "10"
        assert result["led"] == "1"
        assert result["control"] == "A"
        assert result["connection"] == "18"

    def test_parses_simplified_sku_format(self):
        simple_sku = "0162/1"
        result = vibia_price_list.parse_sku_components(simple_sku)
        assert result is not None
        assert result["model"] == "0162"
        assert result["variant_code"] == "1"

    def test_returns_none_for_invalid_format(self):
        invalid_sku = "invalid-sku"
        result = vibia_price_list.parse_sku_components(invalid_sku)
        assert result is None

    def test_handles_whitespace_variations(self):
        sku_with_spaces = "1160  10  /  1A  _  18"
        result = vibia_price_list.parse_sku_components(sku_with_spaces)
        assert result is not None  # Regex handles extra whitespace
        assert result["model"] == "1160"


class TestBuildFullSku:
    """Tests for build_full_sku function."""

    def test_builds_correct_sku_format(self):
        model = "1160"
        surface = "10"
        led = "1"
        control = "A"
        connection = "18"
        result = vibia_price_list.build_full_sku(
            model, surface, led, control, connection
        )
        assert result == "1160 10 / 1A _ 18"

    def test_builds_sku_with_different_components(self):
        model = "0162"
        surface = "24"
        led = "6"
        control = "Z"
        connection = "03"
        result = vibia_price_list.build_full_sku(
            model, surface, led, control, connection
        )
        assert result == "0162 24 / 6Z _ 03"

    def test_built_sku_can_be_parsed_back(self):
        model = "1160"
        surface = "10"
        led = "1"
        control = "A"
        connection = "18"
        built_sku = vibia_price_list.build_full_sku(
            model, surface, led, control, connection
        )
        parsed = vibia_price_list.parse_sku_components(built_sku)
        assert parsed is not None
        assert parsed["model"] == model
        assert parsed["surface"] == surface
        assert parsed["led"] == led
        assert parsed["control"] == control
        assert parsed["connection"] == connection


class TestProductDataStructure:
    """Tests for product data structure consistency."""

    def test_all_products_have_required_fields(self):
        for model, product in vibia_price_list.ALL_PRODUCTS.items():
            assert product["base_sku"] == model
            assert "product_name" in product
            assert "url_slug" in product
            assert "category_prefix" in product
            assert "variants" in product
            assert isinstance(product["variants"], list)

    def test_all_variants_have_consistent_structure(self):
        for product in vibia_price_list.ALL_PRODUCTS.values():
            for variant in product["variants"]:
                assert "sku" in variant
                assert "price_eur" in variant
                assert "surface_code" in variant
                assert "led_code" in variant
                assert "control_code" in variant

    def test_circus_family_shares_same_slug(self):
        circus_models = ["0162", "0167", "0164"]
        for model in circus_models:
            product = vibia_price_list.get_product_by_model(model)
            assert product is not None
            assert product["url_slug"] == "circus"
