"""Unit tests for attribute parsing functions.

Following CLAUDE.md: parameterized inputs, test entire structure, no trivial asserts.
"""

import pytest

from src.scrapers.attribute_parser import (
    clean_variant_header_name,
    extract_certifications_from_html,
    parse_designer_from_title,
    parse_hills_from_text,
    parse_table_header_attributes,
    parse_weight_from_text,
    parse_weight_to_float,
)


@pytest.mark.unit
class TestParseDesignerFromTitle:
    """Test designer extraction from product titles."""

    @pytest.mark.parametrize(
        "title,expected_designer",
        [
            ("Kelly, design by Andrea Tosetto, 2015", "Andrea Tosetto"),
            ("A-Tube Nano, design by Lodes, 2016", "Lodes"),
            ("Flask, Design by Studio Italia Design", "Studio Italia Design"),
            ("Product Name, DESIGN BY John Doe, 2020", "John Doe"),
            ("Lamp, design by Designer Name Inc.", "Designer Name Inc."),
        ],
    )
    def test_parse_designer_from_valid_titles(self, title: str, expected_designer: str):
        """Test designer extraction from various valid title formats."""
        result = parse_designer_from_title(title)
        assert result == expected_designer

    @pytest.mark.parametrize(
        "title",
        [
            "Product Name Without Designer",
            "",
            "Just a Product, 2020",
            "Design without by keyword",
            None,
        ],
    )
    def test_parse_designer_from_invalid_titles(self, title: str):
        """Test designer extraction returns None for invalid titles."""
        result = parse_designer_from_title(title)
        assert result is None


@pytest.mark.unit
class TestParseTableHeaderAttributes:
    """Test parsing attributes from table headers."""

    def test_parse_valid_header_attributes(self):
        """Test extraction of key-value pairs from headers."""
        headers = [
            "Structure: Metal",
            "Diffuser: Methacrylate",
            "Light source",
            "Cable",
            "Code 2700 K",
        ]

        result = parse_table_header_attributes(headers)

        assert result == {
            "Structure": "Metal",
            "Diffuser": "Methacrylate",
        }

    def test_parse_empty_headers(self):
        """Test parsing empty header list."""
        result = parse_table_header_attributes([])
        assert result == {}

    def test_parse_headers_with_whitespace(self):
        """Test parsing handles extra whitespace."""
        headers = [
            "  Structure:  Metal  ",
            " Diffuser : Glass ",
        ]

        result = parse_table_header_attributes(headers)

        assert result == {
            "Structure": "Metal",
            "Diffuser": "Glass",
        }

    def test_parse_ignores_code_headers(self):
        """Test Code headers are not extracted as attributes."""
        headers = [
            "Code 2700 K",
            "Code 3000 K",
            "Structure: Metal",
        ]

        result = parse_table_header_attributes(headers)

        assert result == {"Structure": "Metal"}


@pytest.mark.unit
class TestParseWeightFromText:
    """Test weight extraction from text."""

    @pytest.mark.parametrize(
        "text,expected_weight",
        [
            ("Net weight: 0.22 kg", "0.22 kg"),
            ("Net weight: 6.00 kg", "6.00 kg"),
            ("NET WEIGHT: 1.5 kg", "1.5 kg"),
            ("Some text Net weight: 10.5 kg more text", "10.5 kg"),
        ],
    )
    def test_parse_weight_from_valid_text(self, text: str, expected_weight: str):
        """Test weight extraction from various valid formats."""
        result = parse_weight_from_text(text)
        assert result == expected_weight

    @pytest.mark.parametrize(
        "text,expected_weight",
        [
            # German format with comma decimal separator
            ("Nettogewicht: 0,40 kg", "0.40 kg"),
            ("Nettogewicht: 6,00 kg", "6.00 kg"),
            # Italian format
            ("Peso netto: 6.00 kg", "6.00 kg"),
            ("Peso netto: 0,40 kg", "0.40 kg"),
            # Mixed case
            ("NETTOGEWICHT: 2,5 kg", "2.5 kg"),
            ("peso NETTO: 1.25 kg", "1.25 kg"),
        ],
    )
    def test_parse_weight_multilingual(self, text: str, expected_weight: str):
        """Test weight extraction supports German and Italian."""
        result = parse_weight_from_text(text)
        assert result == expected_weight

    @pytest.mark.parametrize(
        "text",
        [
            "No weight here",
            "",
            "Weight: 5 pounds",
            None,
        ],
    )
    def test_parse_weight_from_invalid_text(self, text: str):
        """Test weight extraction returns None for invalid input."""
        result = parse_weight_from_text(text)
        assert result is None


@pytest.mark.unit
class TestParseHillsFromText:
    """Test hills extraction from text."""

    @pytest.mark.parametrize(
        "text,expected_hills",
        [
            ("Hills: 2", "2"),
            ("Hills: 10", "10"),
            ("Some text Hills: 5 more text", "5"),
        ],
    )
    def test_parse_hills_from_valid_text(self, text: str, expected_hills: str):
        """Test hills extraction from valid text."""
        result = parse_hills_from_text(text)
        assert result == expected_hills

    @pytest.mark.parametrize(
        "text",
        [
            "No hills here",
            "",
            None,
        ],
    )
    def test_parse_hills_from_invalid_text(self, text: str):
        """Test hills extraction returns None for invalid input."""
        result = parse_hills_from_text(text)
        assert result is None


@pytest.mark.unit
class TestParseWeightToFloat:
    """Test weight string to float conversion."""

    @pytest.mark.parametrize(
        "weight_str,expected_float",
        [
            ("0.40 kg", 0.40),
            ("6.00 kg", 6.00),
            ("1.5 kg", 1.5),
            ("10 kg", 10.0),
            ("0.22 kg", 0.22),
            # Edge cases
            ("5kg", 5.0),  # No space
            ("  2.5 kg  ", 2.5),  # Extra whitespace
        ],
    )
    def test_parse_weight_to_float_valid(self, weight_str: str, expected_float: float):
        """Test conversion of valid weight strings to float."""
        result = parse_weight_to_float(weight_str)
        assert result == expected_float

    @pytest.mark.parametrize(
        "weight_str",
        [
            None,
            "",
            "invalid",
            "kg only",
            "no numbers here",
        ],
    )
    def test_parse_weight_to_float_invalid(self, weight_str: str):
        """Test conversion returns None for invalid input."""
        result = parse_weight_to_float(weight_str)
        assert result is None


@pytest.mark.unit
class TestExtractCertificationsFromHtml:
    """Test certification extraction from HTML."""

    def test_extract_all_certifications(self):
        """Test extraction of multiple certifications."""
        html = """
        <div>
            IP 20 rating
            220-240V voltage
            CE mark
        </div>
        """

        result = extract_certifications_from_html(html)

        assert result == {
            "IP Rating": "20",
            "Voltage": "220-240V",
            "Certification": "CE",
        }

    def test_extract_partial_certifications(self):
        """Test extraction when only some certifications present."""
        html = "<div>IP 40 rating</div>"

        result = extract_certifications_from_html(html)

        assert result == {"IP Rating": "40"}

    def test_extract_no_certifications(self):
        """Test extraction from HTML with no certifications."""
        html = "<div>No certifications here</div>"

        result = extract_certifications_from_html(html)

        assert result == {}

    def test_extract_voltage_variations(self):
        """Test voltage extraction handles different formats."""
        html1 = "100-240V"
        html2 = "220–240V"

        result1 = extract_certifications_from_html(html1)
        result2 = extract_certifications_from_html(html2)

        assert result1["Voltage"] == "100-240V"
        assert result2["Voltage"] == "220–240V"


@pytest.mark.unit
class TestCleanVariantHeaderName:
    """Test cleaning of variant table header names."""

    @pytest.mark.parametrize(
        "header_text,expected_cleaned",
        [
            ("Diffusore: Vetro", "Diffusore"),
            ("Structure: Metal", "Structure"),
            ("Codice", "Codice"),
            ("Code", "Code"),
            ("Variant Type: Large", "Variant Type"),
            ("Color: Black", "Color"),
            ("  Diffusore: Vetro  ", "Diffusore"),  # With whitespace
            ("", ""),  # Empty string
        ],
    )
    def test_clean_header_with_colon(self, header_text: str, expected_cleaned: str):
        """Should extract attribute name from header text with colon."""
        result = clean_variant_header_name(header_text)
        assert result == expected_cleaned

    def test_clean_header_without_colon(self):
        """Should return header as-is when no colon present."""
        result = clean_variant_header_name("Codice")
        assert result == "Codice"

    def test_clean_header_multiple_colons(self):
        """Should split on first colon only."""
        result = clean_variant_header_name("Attribute: Value: Extra")
        assert result == "Attribute"

    def test_clean_header_none(self):
        """Should return empty string for None input."""
        result = clean_variant_header_name(None)
        assert result == ""

    @pytest.mark.parametrize(
        "invalid_header",
        [
            "Kelly medium dome 60",
            "A-Tube small pendant 40",
            "Product large size 80",
        ],
    )
    def test_filter_out_variant_names(self, invalid_header: str):
        """Should filter out headers that look like variant names."""
        result = clean_variant_header_name(invalid_header)
        assert result == ""

    @pytest.mark.parametrize(
        "valid_header",
        [
            "Codice",
            "Code",
            "Structure",
            "Diffusore",
            "Color",
            "Variant Type",
        ],
    )
    def test_keep_valid_attribute_names(self, valid_header: str):
        """Should keep headers that are valid attribute names."""
        result = clean_variant_header_name(valid_header)
        assert result == valid_header
