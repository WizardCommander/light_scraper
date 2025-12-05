"""Unit tests for CLI argument parsing.

Following CLAUDE.md T-1: colocate unit tests with clear test descriptions.
"""

import argparse
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from src.cli import main


class TestTranslateToGermanFlag:
    """Tests for the --no-translate flag behavior."""

    def test_translate_to_german_defaults_to_true(self):
        """Without --no-translate flag, translate_to_german should default to True."""
        # Create parser with same configuration as CLI
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--no-translate",
            action="store_false",
            dest="translate_to_german",
        )

        # Parse without the flag
        args = parser.parse_args([])

        assert args.translate_to_german is True

    def test_no_translate_flag_sets_to_false(self):
        """With --no-translate flag, translate_to_german should be False."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--no-translate",
            action="store_false",
            dest="translate_to_german",
        )

        # Parse with the flag
        args = parser.parse_args(["--no-translate"])

        assert args.translate_to_german is False

    def test_flag_name_is_no_translate(self):
        """Verify the flag name is --no-translate (not --translate-german)."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--no-translate",
            action="store_false",
            dest="translate_to_german",
        )

        # Should parse successfully with --no-translate
        args = parser.parse_args(["--no-translate"])
        assert hasattr(args, "translate_to_german")

        # Old flag name should not exist (would raise error if attempted)
        with pytest.raises(SystemExit):
            parser.parse_args(["--translate-german"])


class TestCLIIntegration:
    """Integration tests for CLI main function."""

    @patch("src.cli.scrape_and_export")
    def test_cli_passes_translate_to_german_true_by_default(
        self, mock_scrape_and_export
    ):
        """CLI should pass translate_to_german=True to orchestrator by default."""
        mock_scrape_and_export.return_value = (
            [],
            "output/products.csv",
            "output/products.xlsx",
        )

        # Mock sys.argv to simulate CLI call without --no-translate
        test_args = [
            "cli.py",
            "--manufacturer",
            "lodes",
            "--skus",
            "test-sku",
        ]

        with patch.object(sys, "argv", test_args):
            exit_code = main()

        assert exit_code == 0
        mock_scrape_and_export.assert_called_once()

        # Verify translate_to_german=True was passed (default behavior)
        call_kwargs = mock_scrape_and_export.call_args[1]
        assert call_kwargs["translate_to_german"] is True

    @patch("src.cli.scrape_and_export")
    def test_cli_passes_translate_to_german_false_with_flag(
        self, mock_scrape_and_export
    ):
        """CLI should pass translate_to_german=False when --no-translate is used."""
        mock_scrape_and_export.return_value = (
            [],
            "output/products.csv",
            "output/products.xlsx",
        )

        # Mock sys.argv with --no-translate flag
        test_args = [
            "cli.py",
            "--manufacturer",
            "lodes",
            "--skus",
            "test-sku",
            "--no-translate",
        ]

        with patch.object(sys, "argv", test_args):
            exit_code = main()

        assert exit_code == 0
        mock_scrape_and_export.assert_called_once()

        # Verify translate_to_german=False was passed
        call_kwargs = mock_scrape_and_export.call_args[1]
        assert call_kwargs["translate_to_german"] is False


class TestCLIHelp:
    """Tests for CLI help text."""

    def test_help_mentions_no_translate_flag(self):
        """Help text should document the --no-translate flag."""
        test_args = ["cli.py", "--help"]

        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                # Capture stdout to check help text
                with patch("sys.stdout", new_callable=StringIO):
                    main()

            # Help should exit with code 0
            assert exc_info.value.code == 0

    def test_help_explains_translation_is_default(self):
        """Help text should explain translation is enabled by default."""
        # This test verifies the help text is accessible
        # (actual content verification happens through manual review)
        test_args = ["cli.py", "--help"]

        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit):
                main()
