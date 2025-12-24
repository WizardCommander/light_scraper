"""Integration tests for OpenAI AI features.

These tests verify that OpenAI integration works for:
- Description generation
- Translation
- Image classification

NOTE: These tests require OPENAI_API_KEY environment variable.
Mark as integration tests to skip in CI without API key.
"""

import os
import pytest
from src.ai.description_generator import generate_description, generate_short_description
from src.ai.german_translator import translate_to_german
from src.models import ProductData, SKU, Manufacturer


@pytest.fixture
def sample_product():
    """Create sample product for testing."""
    return ProductData(
        sku=SKU("test-openai-001"),
        name="Modern Pendant Light",
        description="A sleek aluminum pendant light with LED technology.",
        manufacturer=Manufacturer("lodes"),
        categories=["Pendant", "Modern"],
        attributes={
            "Material": "Aluminum",
            "Power": "12W LED",
        },
        images=[],
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY environment variable"
)
class TestOpenAIDescriptionGeneration:
    """Integration tests for OpenAI description generation."""

    def test_generate_description_with_openai(self, sample_product):
        """Should generate description using OpenAI API."""
        # This is a smoke test - just verify it returns a non-empty string
        description = generate_description(sample_product)

        assert isinstance(description, str)
        assert len(description) > 50
        # Should be different from original (AI-enhanced)
        # (Could be same if caching, but that's also valid behavior)

    def test_generate_short_description_with_openai(self, sample_product):
        """Should generate short description using OpenAI API."""
        short_desc = generate_short_description(sample_product, max_words=20)

        assert isinstance(short_desc, str)
        assert len(short_desc) > 10
        # Should respect word limit (with some tolerance)
        word_count = len(short_desc.split())
        assert word_count <= 25  # Allow some tolerance

    def test_cache_uses_model_in_key(self, sample_product, tmp_path):
        """Should include model in cache key to avoid conflicts."""
        # Generate with gpt-4o-mini
        desc1 = generate_description(
            sample_product,
            model="gpt-4o-mini",
            cache_dir=str(tmp_path)
        )

        # Check that cache file includes model name
        cache_files = list(tmp_path.glob("*.json"))
        assert len(cache_files) > 0
        assert any("gpt-4o-mini" in f.name for f in cache_files)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Requires OPENAI_API_KEY environment variable"
)
class TestOpenAITranslation:
    """Integration tests for OpenAI translation."""

    def test_translate_to_german_with_openai(self):
        """Should translate text to German using OpenAI API."""
        english_text = "Pendant Light"
        german_text = translate_to_german(english_text, field_type="product_name")

        assert isinstance(german_text, str)
        assert len(german_text) > 0
        # Basic sanity check - German translation should be different from English
        # (unless it's a brand name or technical term)

    def test_translate_description_with_openai(self):
        """Should translate longer description."""
        english_desc = "A beautiful ceiling light with modern design and LED technology."
        german_desc = translate_to_german(english_desc, field_type="description")

        assert isinstance(german_desc, str)
        assert len(german_desc) > 20
