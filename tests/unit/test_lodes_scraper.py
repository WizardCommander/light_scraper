"""Unit tests for Lodes scraper helper functions.

Following CLAUDE.md: parameterized inputs, test entire structure, no trivial asserts.
"""

import pytest

from src.models import SKU, ImageUrl
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
    """Test product URL construction from SKU with language support."""
    scraper = LodesScraper()
    sku = SKU("kelly")

    # Test English URL (uses "products")
    url_en = scraper.build_product_url(sku, language="en")
    assert url_en == "https://www.lodes.com/en/products/kelly/"
    assert "/products/" in url_en

    # Test German URL (uses "producten")
    url_de = scraper.build_product_url(sku, language="de")
    assert url_de == "https://www.lodes.com/de/producten/kelly/"
    assert "/producten/" in url_de

    # Test default (English)
    url_default = scraper.build_product_url(sku)
    assert url_default == "https://www.lodes.com/en/products/kelly/"


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


@pytest.mark.unit
class TestExtractVariationAttributeNames:
    """Test extraction of variation attribute names from variant data."""

    def test_extract_from_multiple_variants(self):
        """Should extract all unique attribute names from variants."""
        variants = [
            {"Code": "SKU1", "Structure": "Metal", "Diffusor": "Glass"},
            {"Code": "SKU2", "Structure": "Wood", "Diffusor": "Plastic"},
            {"Code": "SKU3", "Structure": "Metal", "Color": "Black"},
        ]

        result = LodesScraper._extract_variation_attribute_names(variants)

        assert result == {"Structure", "Diffusor", "Color"}
        assert "Code" not in result

    def test_extract_excludes_code_field(self):
        """Should exclude 'Code' from variation attributes."""
        variants = [
            {"Code": "SKU1", "Structure": "Metal"},
            {"Code": "SKU2", "Structure": "Wood"},
        ]

        result = LodesScraper._extract_variation_attribute_names(variants)

        assert "Code" not in result
        assert result == {"Structure"}

    def test_extract_from_empty_variants(self):
        """Should return empty set for empty variant list."""
        variants = []

        result = LodesScraper._extract_variation_attribute_names(variants)

        assert result == set()

    def test_extract_handles_variants_with_only_code(self):
        """Should return empty set when variants only have Code field."""
        variants = [
            {"Code": "SKU1"},
            {"Code": "SKU2"},
        ]

        result = LodesScraper._extract_variation_attribute_names(variants)

        assert result == set()


@pytest.mark.unit
class TestBuildParentVariationAttributes:
    """Test building comma-separated variation attributes for parent product."""

    def test_build_with_two_attributes(self):
        """Should create comma-separated list of all attribute values."""
        variants = [
            {"Code": "SKU1", "Structure": "Metal", "Diffusor": "Glass"},
            {"Code": "SKU2", "Structure": "Wood", "Diffusor": "Plastic"},
            {"Code": "SKU3", "Structure": "Aluminum", "Diffusor": "Glass"},
        ]
        variation_attr_names = {"Structure", "Diffusor"}

        result = LodesScraper._build_parent_variation_attributes(
            variants, variation_attr_names
        )

        assert "Structure" in result
        assert "Diffusor" in result
        # Check all unique values are present
        assert "Metal" in result["Structure"]
        assert "Wood" in result["Structure"]
        assert "Aluminum" in result["Structure"]
        assert "Glass" in result["Diffusor"]
        assert "Plastic" in result["Diffusor"]
        # Check they're comma-separated (order may vary)
        structure_values = set(result["Structure"].split(", "))
        assert structure_values == {"Metal", "Wood", "Aluminum"}
        diffusor_values = set(result["Diffusor"].split(", "))
        assert diffusor_values == {"Glass", "Plastic"}

    def test_build_removes_duplicates(self):
        """Should remove duplicate values in variation attributes."""
        variants = [
            {"Structure": "Metal"},
            {"Structure": "Metal"},
            {"Structure": "Wood"},
        ]
        variation_attr_names = {"Structure"}

        result = LodesScraper._build_parent_variation_attributes(
            variants, variation_attr_names
        )

        structure_values = set(result["Structure"].split(", "))
        assert structure_values == {"Metal", "Wood"}
        assert result["Structure"].count("Metal") == 1

    def test_build_handles_missing_attributes(self):
        """Should handle variants with missing attributes."""
        variants = [
            {"Structure": "Metal", "Color": "Black"},
            {"Structure": "Wood"},  # Missing Color
            {"Color": "White"},  # Missing Structure
        ]
        variation_attr_names = {"Structure", "Color"}

        result = LodesScraper._build_parent_variation_attributes(
            variants, variation_attr_names
        )

        assert "Structure" in result
        assert "Color" in result
        structure_values = set(result["Structure"].split(", "))
        color_values = set(result["Color"].split(", "))
        assert structure_values == {"Metal", "Wood"}
        assert color_values == {"Black", "White"}

    def test_build_with_empty_variants(self):
        """Should return empty dict for empty variants."""
        variants = []
        variation_attr_names = {"Structure"}

        result = LodesScraper._build_parent_variation_attributes(
            variants, variation_attr_names
        )

        assert result == {}


@pytest.mark.unit
class TestBuildVariationName:
    """Test building variation product names."""

    def test_build_with_variation_attributes(self):
        """Should use Code if available, otherwise attributes."""
        parent_name = "Kelly Ceiling Light"

        # Test with Code - should use Code
        variant_with_code = {
            "Code": "14126 1000",
            "Structure": "Metal",
            "Diffusor": "Glass",
        }
        variation_attr_names = {"Structure", "Diffusor"}
        result_with_code = LodesScraper._build_variation_name(
            parent_name, variant_with_code, variation_attr_names, 0
        )
        assert result_with_code == "Kelly Ceiling Light 14126 1000"

        # Test without Code - should use attributes (max 2)
        variant_no_code = {"Structure": "Metal", "Diffusor": "Glass"}
        result_no_code = LodesScraper._build_variation_name(
            parent_name, variant_no_code, variation_attr_names, 0
        )
        assert parent_name in result_no_code
        assert "Metal" in result_no_code or "Glass" in result_no_code
        assert " " in result_no_code

    def test_build_with_single_attribute(self):
        """Should use Code if available, otherwise single attribute."""
        parent_name = "A-Tube Suspension"

        # Without Code - should use attribute
        variant_no_code = {"Structure": "Aluminum"}
        variation_attr_names = {"Structure"}
        result = LodesScraper._build_variation_name(
            parent_name, variant_no_code, variation_attr_names, 0
        )
        assert result == "A-Tube Suspension Aluminum"

        # With Code - should use Code
        variant_with_code = {"Code": "AT-001", "Structure": "Aluminum"}
        result_with_code = LodesScraper._build_variation_name(
            parent_name, variant_with_code, variation_attr_names, 0
        )
        assert result_with_code == "A-Tube Suspension AT-001"

    def test_build_with_no_matching_attributes(self):
        """Should use Code if available, otherwise fall back to variant index."""
        parent_name = "Test Product"
        variant_index = 2

        # With Code but no matching attributes - should use Code
        variant_with_code = {"Code": "SKU1", "Random": "Value"}
        variation_attr_names = {"Structure", "Color"}
        result_with_code = LodesScraper._build_variation_name(
            parent_name, variant_with_code, variation_attr_names, variant_index
        )
        assert result_with_code == "Test Product SKU1"

        # Without Code and no matching attributes - should use variant index
        variant_no_code = {"Random": "Value"}
        result_no_code = LodesScraper._build_variation_name(
            parent_name, variant_no_code, variation_attr_names, variant_index
        )
        assert result_no_code == "Test Product Variant 3"  # Index 2 -> Variant 3

    def test_build_with_empty_variant(self):
        """Should use variant index when variant is empty."""
        parent_name = "Test Product"
        variant = {}
        variation_attr_names = {"Structure"}
        variant_index = 0

        result = LodesScraper._build_variation_name(
            parent_name, variant, variation_attr_names, variant_index
        )

        assert result == "Test Product Variant 1"

    @pytest.mark.parametrize(
        "variant_index,expected_suffix",
        [
            (0, "Variant 1"),
            (1, "Variant 2"),
            (9, "Variant 10"),
        ],
    )
    def test_build_fallback_variant_numbering(
        self, variant_index: int, expected_suffix: str
    ):
        """Should use 1-based indexing for variant fallback names."""
        parent_name = "Product"
        variant = {}
        variation_attr_names = {"Structure"}

        result = LodesScraper._build_variation_name(
            parent_name, variant, variation_attr_names, variant_index
        )

        assert result == f"Product {expected_suffix}"


@pytest.mark.unit
class TestBuildVariableProducts:
    """Test building parent + variation products from variant data."""

    def test_build_with_two_variants(self):
        """Should create parent + 2 child variations."""
        scraper = LodesScraper()
        parent_sku = SKU("kelly-base")
        name = "Kelly Ceiling Light"
        description = "Modern ceiling light"
        categories = ["Ceiling", "Modern"]
        attributes = {"Designer": "John Doe"}
        images = [ImageUrl("https://example.com/image.jpg")]
        variants = [
            {"Code": "KELLY-METAL-GLASS", "Structure": "Metal", "Diffusor": "Glass"},
            {"Code": "KELLY-WOOD-PLASTIC", "Structure": "Wood", "Diffusor": "Plastic"},
        ]
        weight_kg = 2.5
        scraped_lang = "en"

        result = scraper._build_variable_products(
            parent_sku,
            name,
            description,
            categories,
            attributes,
            images,
            variants,
            weight_kg,
            dimensions=None,
            light_specs=None,
            installation_manual="",
            cable_length="",
            scraped_lang=scraped_lang,
            url_slug=parent_sku,
        )

        # Should return parent + 2 children = 3 products
        assert len(result) == 3

        # Check parent product
        parent = result[0]
        assert parent.product_type == "variable"
        assert parent.sku == parent_sku  # Parent keeps the reference SKU
        assert parent.name == name
        assert parent.description == description
        assert parent.images == images
        assert parent.variation_attributes is not None
        assert "Structure" in parent.variation_attributes
        assert "Diffusor" in parent.variation_attributes
        # Parent should have comma-separated values
        assert "Metal" in parent.variation_attributes["Structure"]
        assert "Wood" in parent.variation_attributes["Structure"]

        # Check first child variation
        child1 = result[1]
        assert child1.product_type == "variation"
        assert child1.sku == SKU("KELLY-METAL-GLASS")
        assert child1.parent_sku == parent_sku  # References parent SKU
        assert child1.variation_attributes == {
            "Structure": "Metal",
            "Diffusor": "Glass",
        }
        # Name should use Code when available
        assert child1.name == "Kelly Ceiling Light KELLY-METAL-GLASS"

        # Check second child variation
        child2 = result[2]
        assert child2.product_type == "variation"
        assert child2.sku == SKU("KELLY-WOOD-PLASTIC")
        assert child2.parent_sku == parent_sku  # References parent SKU
        assert child2.variation_attributes == {
            "Structure": "Wood",
            "Diffusor": "Plastic",
        }

    def test_build_with_empty_variants(self):
        """Should return empty list when no variants provided."""
        scraper = LodesScraper()
        parent_sku = SKU("test")
        variants = []

        result = scraper._build_variable_products(
            parent_sku,
            "Test",
            "Desc",
            [],
            {},
            [],
            variants,
            None,
            dimensions=None,
            light_specs=None,
            installation_manual="",
            cable_length="",
            scraped_lang="en",
            url_slug=parent_sku,
        )

        assert result == []

    def test_build_with_variant_missing_code(self):
        """Should generate SKU when variant has no Code field."""
        scraper = LodesScraper()
        parent_sku = SKU("test-base")
        variants = [
            {"Structure": "Metal"},  # No Code field
        ]

        result = scraper._build_variable_products(
            parent_sku,
            "Test",
            "Desc",
            [],
            {},
            [],
            variants,
            None,
            None,
            None,
            "",
            "",
            "en",
            url_slug=parent_sku,
        )

        # Should have parent + 1 child
        assert len(result) == 2
        child = result[1]
        # Should generate SKU as parent_sku-1
        assert child.sku == SKU("test-base-1")
