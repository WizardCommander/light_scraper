"""Unit tests for image_classifier.py pure functions."""

from src.ai.image_classifier import (
    _get_cache_key,
    _parse_classification_response,
    CLASSIFICATION_PROMPT,
)


class TestGetCacheKey:
    """Tests for _get_cache_key function."""

    def test_returns_consistent_hash_for_same_url(self):
        """Should return same hash for identical URL."""
        url = "https://example.com/image.jpg"
        result1 = _get_cache_key(url)
        result2 = _get_cache_key(url)

        assert result1 == result2

    def test_returns_different_hash_for_different_urls(self):
        """Should return different hashes for different URLs."""
        url1 = "https://example.com/image1.jpg"
        url2 = "https://example.com/image2.jpg"

        result1 = _get_cache_key(url1)
        result2 = _get_cache_key(url2)

        assert result1 != result2

    def test_returns_32_character_hex_string(self):
        """Should return MD5 hash (32 hex characters)."""
        url = "https://example.com/image.jpg"
        result = _get_cache_key(url)

        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)


class TestParseClassificationResponse:
    """Tests for _parse_classification_response function."""

    def test_returns_product_for_product_response(self):
        """Should return 'product' for 'product' response."""
        result = _parse_classification_response("product")

        assert result == "product"

    def test_returns_project_for_project_response(self):
        """Should return 'project' for 'project' response."""
        result = _parse_classification_response("project")

        assert result == "project"

    def test_handles_uppercase_input(self):
        """Should normalize uppercase input."""
        result = _parse_classification_response("PRODUCT")

        assert result == "product"

    def test_handles_mixed_case_input(self):
        """Should normalize mixed case input."""
        result = _parse_classification_response("PrOjEcT")

        assert result == "project"

    def test_handles_whitespace(self):
        """Should trim whitespace from input."""
        result = _parse_classification_response("  product  ")

        assert result == "product"

    def test_defaults_to_project_for_invalid_input(self):
        """Should default to 'project' for unrecognized response."""
        result = _parse_classification_response("invalid")

        assert result == "project"

    def test_defaults_to_project_for_empty_string(self):
        """Should default to 'project' for empty input."""
        result = _parse_classification_response("")

        assert result == "project"

    def test_defaults_to_project_for_typo(self):
        """Should default to 'project' for common typos."""
        result = _parse_classification_response("prodcut")

        assert result == "project"


class TestClassificationPromptTemplate:
    """Tests for CLASSIFICATION_PROMPT constant."""

    def test_prompt_contains_key_instructions(self):
        """Should contain essential classification instructions."""
        assert "PRODUCT IMAGE" in CLASSIFICATION_PROMPT
        assert "PROJECT IMAGE" in CLASSIFICATION_PROMPT
        assert "White or neutral studio background" in CLASSIFICATION_PROMPT
        assert "Environment/lifestyle" in CLASSIFICATION_PROMPT

    def test_prompt_specifies_exact_response_format(self):
        """Should specify exactly one word response."""
        assert "EXACTLY ONE WORD" in CLASSIFICATION_PROMPT
        assert '"product"' in CLASSIFICATION_PROMPT
        assert '"project"' in CLASSIFICATION_PROMPT

    def test_prompt_is_non_empty_string(self):
        """Should be a substantial prompt."""
        assert isinstance(CLASSIFICATION_PROMPT, str)
        assert len(CLASSIFICATION_PROMPT) > 100
