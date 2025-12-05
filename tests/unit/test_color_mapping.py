"""Unit tests for color name to code mapping in Lodes scraper."""

import pytest

from src.scrapers.lodes_scraper import LodesScraper


class TestMapColorNameToCode:
    """Tests for LodesScraper._map_color_name_to_code method."""

    def setup_method(self):
        """Setup test fixture."""
        self.scraper = LodesScraper()

    def test_maps_italian_bianco_opaco_to_1000(self):
        """Should map 'Bianco Opaco' to code '1000'."""
        code = self.scraper._map_color_name_to_code("Bianco Opaco")

        assert code == "1000"

    def test_maps_italian_nero_opaco_to_2000(self):
        """Should map 'Nero Opaco' to code '2000'."""
        code = self.scraper._map_color_name_to_code("Nero Opaco")

        assert code == "2000"

    def test_maps_italian_bronzo_ramato_to_3500(self):
        """Should map 'Bronzo Ramato' to code '3500'."""
        code = self.scraper._map_color_name_to_code("Bronzo Ramato")

        assert code == "3500"

    def test_maps_italian_champagne_opaco_to_4500(self):
        """Should map 'Champagne Opaco' to code '4500'."""
        code = self.scraper._map_color_name_to_code("Champagne Opaco")

        assert code == "4500"

    def test_maps_english_matte_white_to_1000(self):
        """Should map 'Matte White' to code '1000'."""
        code = self.scraper._map_color_name_to_code("Matte White")

        assert code == "1000"

    def test_maps_english_matte_black_to_2000(self):
        """Should map 'Matte Black' to code '2000'."""
        code = self.scraper._map_color_name_to_code("Matte Black")

        assert code == "2000"

    def test_maps_german_weiss_matt_to_1000(self):
        """Should map 'Weiß Matt' to code '1000'."""
        code = self.scraper._map_color_name_to_code("Weiß Matt")

        assert code == "1000"

    def test_maps_german_schwarz_matt_to_2000(self):
        """Should map 'Schwarz Matt' to code '2000'."""
        code = self.scraper._map_color_name_to_code("Schwarz Matt")

        assert code == "2000"

    def test_removes_color_code_suffix_before_mapping(self):
        """Should remove color code suffix like '– 9005' before mapping."""
        code = self.scraper._map_color_name_to_code("Nero Opaco – 9005")

        assert code == "2000"

    def test_removes_color_code_suffix_with_dash(self):
        """Should remove color code suffix with regular dash."""
        code = self.scraper._map_color_name_to_code("Bianco Opaco - 9010")

        assert code == "1000"

    def test_handles_case_insensitivity(self):
        """Should handle different cases (upper/lower)."""
        code = self.scraper._map_color_name_to_code("NERO OPACO")

        assert code == "2000"

    def test_handles_extra_whitespace(self):
        """Should handle extra whitespace."""
        code = self.scraper._map_color_name_to_code("  Bianco Opaco  ")

        assert code == "1000"

    def test_maps_partial_match_in_longer_text(self):
        """Should find color name within longer text."""
        code = self.scraper._map_color_name_to_code("Kelly dome Nero Opaco finish")

        assert code == "2000"

    def test_returns_none_for_unknown_color(self):
        """Should return None for unknown color name."""
        code = self.scraper._map_color_name_to_code("Unknown Color")

        assert code is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty string."""
        code = self.scraper._map_color_name_to_code("")

        assert code is None

    def test_returns_none_for_none_input(self):
        """Should return None for None input."""
        code = self.scraper._map_color_name_to_code(None)

        assert code is None

    def test_maps_color_code_9010_to_1000(self):
        """Should map RAL code '9010' to color code '1000'."""
        code = self.scraper._map_color_name_to_code("9010")

        assert code == "1000"

    def test_maps_color_code_9005_to_2000(self):
        """Should map RAL code '9005' to color code '2000'."""
        code = self.scraper._map_color_name_to_code("9005")

        assert code == "2000"

    def test_prefers_exact_match_over_partial(self):
        """Should prefer exact match when both exact and partial matches exist."""
        # "bianco" alone should match before "bianco opaco"
        code = self.scraper._map_color_name_to_code("bianco")

        assert code == "1000"

    def test_maps_simple_white_to_1000(self):
        """Should map simple 'White' to code '1000'."""
        code = self.scraper._map_color_name_to_code("White")

        assert code == "1000"

    def test_maps_simple_black_to_2000(self):
        """Should map simple 'Black' to code '2000'."""
        code = self.scraper._map_color_name_to_code("Black")

        assert code == "2000"

    def test_maps_bronze_to_3500(self):
        """Should map 'Bronze' to code '3500'."""
        code = self.scraper._map_color_name_to_code("Bronze")

        assert code == "3500"

    def test_maps_champagne_to_4500(self):
        """Should map 'Champagne' to code '4500'."""
        code = self.scraper._map_color_name_to_code("Champagne")

        assert code == "4500"
