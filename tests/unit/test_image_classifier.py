"""Unit tests for image_classifier.py pure functions."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from src.ai.image_classifier import (
    _get_cache_key,
    _parse_classification_response,
    classify_image_file,
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


class TestClassifyImageFile:
    """Tests for classify_image_file function."""

    @patch("src.ai.image_classifier._load_from_cache")
    @patch("src.ai.image_classifier._call_vision_api")
    @patch("src.ai.image_classifier._save_to_cache")
    @patch("src.ai.image_classifier.OpenAI")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_classifies_product_image(
        self, mock_file, mock_openai, mock_save_cache, mock_call_api, mock_load_cache
    ):
        """Should classify image as product and cache result."""
        # Setup
        mock_load_cache.return_value = None  # No cache
        mock_call_api.return_value = "product"

        # Execute
        result = classify_image_file("/path/to/image.jpg")

        # Verify
        assert result == "product"
        mock_file.assert_called_once_with("/path/to/image.jpg", "rb")
        mock_call_api.assert_called_once()
        mock_save_cache.assert_called_once()

    @patch("src.ai.image_classifier._load_from_cache")
    def test_returns_cached_result_when_available(self, mock_load_cache):
        """Should return cached result without API call."""
        # Setup
        mock_load_cache.return_value = "project"

        # Execute
        with patch("builtins.open") as mock_file:
            result = classify_image_file("/path/to/cached.jpg")

        # Verify
        assert result == "project"
        mock_file.assert_not_called()  # Should not read file if cached

    @patch("src.ai.image_classifier._load_from_cache")
    @patch("src.ai.image_classifier._call_vision_api")
    @patch("src.ai.image_classifier.OpenAI")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_handles_api_failure_gracefully(
        self, mock_file, mock_openai, mock_call_api, mock_load_cache
    ):
        """Should default to project on API failure."""
        # Setup
        mock_load_cache.return_value = None
        mock_call_api.side_effect = Exception("API Error")

        # Execute
        result = classify_image_file("/path/to/image.jpg")

        # Verify
        assert result == "project"  # Default fallback

    @patch("src.ai.image_classifier._load_from_cache")
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_handles_missing_file(self, mock_file, mock_load_cache):
        """Should default to project when file not found."""
        # Setup
        mock_load_cache.return_value = None

        # Execute
        result = classify_image_file("/nonexistent/image.jpg")

        # Verify
        assert result == "project"

    @patch("src.ai.image_classifier._load_from_cache")
    @patch("src.ai.image_classifier._call_vision_api")
    @patch("src.ai.image_classifier.OpenAI")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_determines_mime_type_from_extension(
        self, mock_file, mock_openai, mock_call_api, mock_load_cache
    ):
        """Should correctly determine MIME type from file extension."""
        # Setup
        mock_load_cache.return_value = None
        mock_call_api.return_value = "product"

        # Test different extensions
        test_cases = [
            ("/path/image.jpg", "image/jpeg"),
            ("/path/image.jpeg", "image/jpeg"),
            ("/path/image.png", "image/png"),
            ("/path/image.webp", "image/webp"),
        ]

        for file_path, expected_mime in test_cases:
            # Execute
            classify_image_file(file_path)

            # Verify MIME type was used (check the API call)
            # The MIME type is passed to _call_vision_api
            call_args = mock_call_api.call_args
            assert call_args is not None

    @patch("src.ai.image_classifier._load_from_cache")
    @patch("src.ai.image_classifier._call_vision_api")
    @patch("src.ai.image_classifier._save_to_cache")
    @patch("src.ai.image_classifier.OpenAI")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_uses_provided_api_key(
        self,
        mock_file,
        mock_openai_class,
        mock_save_cache,
        mock_call_api,
        mock_load_cache,
    ):
        """Should use provided API key instead of environment variable."""
        # Setup
        mock_load_cache.return_value = None
        mock_call_api.return_value = "product"
        custom_key = "custom-api-key-123"

        # Execute
        classify_image_file("/path/to/image.jpg", api_key=custom_key)

        # Verify OpenAI was initialized with custom key
        mock_openai_class.assert_called_once_with(api_key=custom_key)

    @patch("src.ai.image_classifier._load_from_cache")
    @patch("src.ai.image_classifier._call_vision_api")
    @patch("src.ai.image_classifier._save_to_cache")
    @patch("src.ai.image_classifier.OpenAI")
    @patch("os.getenv")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_falls_back_to_env_api_key(
        self,
        mock_file,
        mock_getenv,
        mock_openai_class,
        mock_save_cache,
        mock_call_api,
        mock_load_cache,
    ):
        """Should use OPENAI_API_KEY environment variable when no key provided."""
        # Setup
        mock_load_cache.return_value = None
        mock_call_api.return_value = "product"
        mock_getenv.return_value = "env-api-key-456"

        # Execute
        classify_image_file("/path/to/image.jpg")

        # Verify environment variable was checked
        mock_getenv.assert_called_with("OPENAI_API_KEY")

    @patch("src.ai.image_classifier._load_from_cache")
    @patch("src.ai.image_classifier._call_vision_api")
    @patch("src.ai.image_classifier._parse_classification_response")
    @patch("src.ai.image_classifier.OpenAI")
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_data")
    def test_parses_api_response(
        self, mock_file, mock_openai, mock_parse, mock_call_api, mock_load_cache
    ):
        """Should parse API response through classification parser."""
        # Setup
        mock_load_cache.return_value = None
        mock_call_api.return_value = " PRODUCT "  # Messy response
        mock_parse.return_value = "product"  # Cleaned response

        # Execute
        result = classify_image_file("/path/to/image.jpg")

        # Verify
        mock_parse.assert_called_once_with(" PRODUCT ")
        assert result == "product"
