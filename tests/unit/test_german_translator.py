"""Unit tests for German translation module.

Following CLAUDE.md: parameterized inputs, test entire structure, strong assertions.
Tests use mocking to avoid API calls during testing.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest

from src.ai.german_translator import (
    translate_to_german,
    translate_product_data,
    _build_translation_prompt,
    _get_cache_key,
)
from src.models import ProductData, SKU, ImageUrl, Manufacturer


@pytest.fixture
def sample_product():
    """Create sample English product for translation testing."""
    return ProductData(
        sku=SKU("test-product-123"),
        name="Ceiling Light",
        description="A beautiful ceiling light with modern design.",
        manufacturer=Manufacturer("lodes"),
        categories=["Ceiling", "Modern"],
        attributes={
            "Designer": "John Doe",
            "Material": "Aluminum",
        },
        images=[ImageUrl("https://example.com/image1.jpg")],
        scraped_language="en",
    )


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    mock_message.content = "Deckenleuchte"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


class TestTranslateToGerman:
    """Test translate_to_german function."""

    @pytest.mark.unit
    @patch("src.ai.german_translator._load_from_cache")
    @patch("src.ai.german_translator.OpenAI")
    def test_translate_product_name(
        self, mock_openai, mock_load_cache, mock_openai_response
    ):
        """Should translate product name to German."""
        mock_load_cache.return_value = None  # No cached value
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai.return_value = mock_client

        result = translate_to_german("Ceiling Light", field_type="product_name")

        assert result == "Deckenleuchte"
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.unit
    @patch("src.ai.german_translator._load_from_cache")
    @patch("src.ai.german_translator.OpenAI")
    def test_translate_description(self, mock_openai, mock_load_cache):
        """Should translate description to German."""
        mock_load_cache.return_value = None  # No cached value
        mock_client = MagicMock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Eine schöne Deckenleuchte mit modernem Design."
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = translate_to_german(
            "A beautiful ceiling light with modern design.",
            field_type="description",
        )

        assert "schöne" in result
        assert "Deckenleuchte" in result

    @pytest.mark.unit
    def test_translate_empty_string_returns_original(self):
        """Should return original text when given empty string."""
        assert translate_to_german("", field_type="product_name") == ""
        assert translate_to_german("   ", field_type="product_name") == "   "

    @pytest.mark.unit
    @patch("src.ai.german_translator.OpenAI")
    def test_translate_api_failure_returns_original(self, mock_openai):
        """Should return original text when API fails."""
        mock_openai.return_value.chat.completions.create.side_effect = Exception("API Error")

        original_text = "Test Product"
        result = translate_to_german(original_text, field_type="product_name")

        assert result == original_text

    @pytest.mark.unit
    @patch("src.ai.german_translator._load_from_cache")
    @patch("src.ai.german_translator.OpenAI")
    def test_translate_uses_cache_when_available(self, mock_openai, mock_load_cache):
        """Should use cached translation without API call."""
        mock_load_cache.return_value = "Cached Deckenleuchte"

        result = translate_to_german("Ceiling Light", field_type="product_name")

        assert result == "Cached Deckenleuchte"
        mock_openai.assert_not_called()

    @pytest.mark.unit
    @patch("src.ai.german_translator._load_from_cache")
    @patch("src.ai.german_translator._save_to_cache")
    @patch("src.ai.german_translator.OpenAI")
    def test_translate_saves_to_cache(
        self, mock_openai, mock_save_cache, mock_load_cache, mock_openai_response
    ):
        """Should save translation to cache after API call."""
        mock_load_cache.return_value = None  # No cached value
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai.return_value = mock_client

        translate_to_german("Ceiling Light", field_type="product_name")

        mock_save_cache.assert_called_once()
        call_args = mock_save_cache.call_args
        assert call_args[0][1] == "Deckenleuchte"


class TestTranslateProductData:
    """Test translate_product_data function."""

    @pytest.mark.unit
    @patch("src.ai.german_translator.translate_to_german")
    def test_translate_all_product_fields(self, mock_translate, sample_product):
        """Should translate name, description, and categories."""
        mock_translate.side_effect = [
            "Deckenleuchte",  # name
            "Eine schöne Deckenleuchte mit modernem Design.",  # description
            "Decke",  # category 1
            "Modern",  # category 2
            "John Doe",  # attribute Designer
            "Aluminium",  # attribute Material
        ]

        result = translate_product_data(sample_product)

        assert result.name == "Deckenleuchte"
        assert "Deckenleuchte" in result.description
        assert "Decke" in result.categories
        assert result.attributes["Designer"] == "John Doe"
        assert result.attributes["Material"] == "Aluminium"

    @pytest.mark.unit
    @patch("src.ai.german_translator.translate_to_german")
    def test_translate_preserves_non_text_fields(self, mock_translate, sample_product):
        """Should preserve SKU, images, manufacturer, etc."""
        mock_translate.return_value = "Translated"

        result = translate_product_data(sample_product)

        assert result.sku == sample_product.sku
        assert result.images == sample_product.images
        assert result.manufacturer == sample_product.manufacturer
        assert result.scraped_language == "de"  # Language becomes German after translation
        assert result.translated_to_german is True

    @pytest.mark.unit
    @patch("src.ai.german_translator.translate_to_german")
    def test_translate_handles_empty_categories(self, mock_translate):
        """Should handle products with empty category list."""
        product = ProductData(
            sku=SKU("test"),
            name="Test",
            description="Test description",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
        )

        mock_translate.return_value = "Translated"
        result = translate_product_data(product)

        assert result.categories == []

    @pytest.mark.unit
    @patch("src.ai.german_translator.translate_to_german")
    def test_translate_handles_none_attribute_values(self, mock_translate):
        """Should skip None attribute values during translation."""
        product = ProductData(
            sku=SKU("test"),
            name="Test",
            description="Test description",
            manufacturer=Manufacturer("lodes"),
            categories=["Test"],
            attributes={"Key1": "Value1", "Key2": None, "Key3": ""},
            images=[],
        )

        mock_translate.side_effect = ["Name", "Desc", "Cat", "Value1"]
        translate_product_data(product)

        # Should only translate non-empty string values
        assert mock_translate.call_count == 4  # name, desc, category, Key1 value


class TestBuildTranslationPrompt:
    """Test _build_translation_prompt function."""

    @pytest.mark.unit
    def test_prompt_for_product_name(self):
        """Should build appropriate prompt for product name."""
        prompt = _build_translation_prompt(
            "Ceiling Light", "product_name", "lighting product"
        )

        assert "product name" in prompt.lower()
        assert "Ceiling Light" in prompt
        assert "german" in prompt.lower()

    @pytest.mark.unit
    def test_prompt_for_description(self):
        """Should build appropriate prompt for description."""
        prompt = _build_translation_prompt(
            "Beautiful light", "description", "lighting product"
        )

        assert "description" in prompt.lower()
        assert "Beautiful light" in prompt

    @pytest.mark.unit
    def test_prompt_includes_industry_terminology_guidance(self):
        """Should include guidance for lighting terminology."""
        prompt = _build_translation_prompt(
            "Pendant Light", "product_name", "lighting product"
        )

        assert "lighting" in prompt.lower() or "industry" in prompt.lower()
        assert "terminology" in prompt.lower()


class TestCacheKeyGeneration:
    """Test cache key generation."""

    @pytest.mark.unit
    def test_cache_key_is_deterministic(self):
        """Should generate same key for same input."""
        key1 = _get_cache_key("Test Text", "product_name")
        key2 = _get_cache_key("Test Text", "product_name")

        assert key1 == key2

    @pytest.mark.unit
    def test_cache_key_differs_for_different_text(self):
        """Should generate different keys for different text."""
        key1 = _get_cache_key("Text A", "product_name")
        key2 = _get_cache_key("Text B", "product_name")

        assert key1 != key2

    @pytest.mark.unit
    def test_cache_key_differs_for_different_field_types(self):
        """Should generate different keys for different field types."""
        key1 = _get_cache_key("Test", "product_name")
        key2 = _get_cache_key("Test", "description")

        assert key1 != key2

    @pytest.mark.unit
    def test_cache_key_is_valid_hash(self):
        """Should return valid SHA256 hash."""
        key = _get_cache_key("Test", "product_name")

        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 hex digest length
        assert all(c in "0123456789abcdef" for c in key)
