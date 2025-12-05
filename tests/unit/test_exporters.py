"""Unit tests for exporters.

Following CLAUDE.md: parameterized inputs, test entire structure, no trivial asserts.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.models import ProductData, SKU, ImageUrl, Manufacturer
from src.exporters.woocommerce_csv import (
    export_to_woocommerce_csv,
    format_german_decimal,
    translate_colors_to_german,
    _map_woocommerce_attributes,
    build_short_description_html,
)
from src.exporters.excel_exporter import export_to_excel


@pytest.fixture
def sample_product():
    """Create sample product for testing."""
    return ProductData(
        sku=SKU("test-product-123"),
        name="Test Ceiling Light",
        description="A beautiful test ceiling light with modern design.",
        manufacturer=Manufacturer("lodes"),
        categories=["Ceiling", "Modern"],
        attributes={
            "Designer": "Test Designer",
            "Material": "Aluminum",
            "Weight": "2.5kg",
        },
        images=[
            ImageUrl("https://example.com/image1.jpg"),
            ImageUrl("https://example.com/image2.jpg"),
        ],
        regular_price=299.99,
        stock=10,
    )


@pytest.fixture
def multiple_products(sample_product):
    """Create list of products for batch testing."""
    return [
        sample_product,
        ProductData(
            sku=SKU("test-product-456"),
            name="Test Wall Light",
            description="A modern wall-mounted light fixture.",
            manufacturer=Manufacturer("lodes"),
            categories=["Wall", "Modern"],
            attributes={"Material": "Steel"},
            images=[ImageUrl("https://example.com/image3.jpg")],
            regular_price=199.99,
        ),
    ]


@pytest.mark.unit
def test_export_to_woocommerce_csv_creates_file(sample_product):
    """Test CSV export creates a file with correct name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        result_path = export_to_woocommerce_csv([sample_product], output_path)

        assert Path(result_path).exists()
        assert result_path == Path(output_path)


@pytest.mark.unit
def test_woocommerce_csv_contains_correct_columns(sample_product):
    """Test CSV contains all required WooCommerce German columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path, encoding="utf-8-sig", sep=";")

        # Check for key WooCommerce columns (German names)
        required_columns = [
            "ID",
            "Typ",
            "SKU",
            "Name",
            "Beschreibung",
            "Bilder",
            "Regulärer Preis",
            "Attribut 1 Name",
            "Attribut 1 Wert(e)",
        ]

        for col in required_columns:
            assert col in df.columns, f"Missing column: {col}"


@pytest.mark.unit
def test_woocommerce_csv_product_data_accuracy(sample_product):
    """Test CSV accurately represents product data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(
            output_path, encoding="utf-8-sig", sep=";", keep_default_na=False
        )
        row = df.iloc[0]

        assert row["SKU"] == "test-product-123"
        assert row["Name"] == "Test Ceiling Light"
        assert "modern design" in row["Beschreibung"].lower()
        assert row["Regulärer Preis"] == "299,99"  # German decimal format
        assert str(row["Vorrätig?"]) == "1"


@pytest.mark.unit
def test_woocommerce_csv_images_comma_separated(sample_product):
    """Test images are comma-separated in CSV output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path, encoding="utf-8-sig", sep=";")
        row = df.iloc[0]

        images = row["Bilder"]
        assert "," in images
        assert "image1.jpg" in images
        assert "image2.jpg" in images


@pytest.mark.unit
def test_woocommerce_csv_attributes_mapped_to_standard_columns(sample_product):
    """Test product attributes are mapped to standard WooCommerce attribute columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(
            output_path, encoding="utf-8-sig", sep=";", keep_default_na=False
        )
        row = df.iloc[0]

        # Test that German attribute names are used
        assert row["Attribut 1 Name"] == "Farbe"
        assert row["Attribut 2 Name"] == "Lichtfarbe"
        assert row["Attribut 3 Name"] == "Dimmbarkeit"
        assert row["Attribut 4 Name"] == "Montage"


@pytest.mark.unit
def test_woocommerce_csv_all_columns_present(sample_product):
    """Test that all WooCommerce columns are present (no missing columns)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path, encoding="utf-8-sig", sep=";")

        # Should have exactly 76 columns (57 standard + 19 new)
        expected_column_count = 76
        assert len(df.columns) == expected_column_count


@pytest.mark.unit
def test_woocommerce_csv_no_meta_columns(sample_product):
    """Test that CSV doesn't include meta: columns (only standard columns)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path, encoding="utf-8-sig", sep=";")

        # Check that no columns start with "meta:"
        meta_columns = [col for col in df.columns if col.startswith("meta:")]
        assert len(meta_columns) == 0


@pytest.mark.unit
def test_woocommerce_csv_format_matches_schema(sample_product):
    """Test CSV format matches WooCommerce import schema requirements."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(
            output_path, encoding="utf-8-sig", sep=";", keep_default_na=False
        )
        row = df.iloc[0]

        # Veröffentlicht should be 1 (published - matching client CSV)
        assert int(row["Veröffentlicht"]) == 1

        # Steuerklasse should be "parent"
        assert row["Steuerklasse"] == "parent"

        # Schlagwörter should be populated
        assert len(row["Schlagwörter"]) > 0


@pytest.mark.unit
def test_woocommerce_csv_empty_list_raises_error():
    """Test that exporting empty product list raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"

        with pytest.raises(ValueError, match="Cannot export empty product list"):
            export_to_woocommerce_csv([], output_path)


@pytest.mark.unit
def test_export_to_excel_creates_file(sample_product):
    """Test Excel export creates a file with correct name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.xlsx"
        result_path = export_to_excel([sample_product], output_path)

        assert Path(result_path).exists()
        assert result_path == Path(output_path)


@pytest.mark.unit
def test_excel_export_product_data_accuracy(sample_product):
    """Test Excel file accurately represents product data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.xlsx"
        export_to_excel([sample_product], output_path)

        df = pd.read_excel(output_path)
        row = df.iloc[0]

        assert row["SKU"] == "test-product-123"
        assert row["Name"] == "Test Ceiling Light"
        assert "modern design" in row["Description"].lower()
        assert row["Regular Price"] == 299.99


@pytest.mark.unit
def test_excel_export_attributes_as_columns(sample_product):
    """Test attributes are exported as separate columns in Excel."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.xlsx"
        export_to_excel([sample_product], output_path)

        df = pd.read_excel(output_path)

        # Check that attributes are exported as "Attr: " prefixed columns
        assert "Attr: Designer" in df.columns
        assert df.iloc[0]["Attr: Designer"] == "Test Designer"


@pytest.mark.unit
def test_excel_export_empty_list_raises_error():
    """Test that exporting empty product list raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.xlsx"

        with pytest.raises(ValueError, match="Cannot export empty product list"):
            export_to_excel([], output_path)


@pytest.mark.unit
def test_batch_export_multiple_products(multiple_products):
    """Test exporting multiple products maintains data integrity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = f"{tmpdir}/test_products.csv"
        excel_path = f"{tmpdir}/test_products.xlsx"

        export_to_woocommerce_csv(multiple_products, csv_path)
        export_to_excel(multiple_products, excel_path)

        # Check CSV
        csv_df = pd.read_csv(csv_path, encoding="utf-8-sig", sep=";")
        assert len(csv_df) == 2
        assert csv_df.iloc[0]["SKU"] == "test-product-123"
        assert csv_df.iloc[1]["SKU"] == "test-product-456"

        # Check Excel
        excel_df = pd.read_excel(excel_path)
        assert len(excel_df) == 2
        assert excel_df.iloc[0]["SKU"] == "test-product-123"
        assert excel_df.iloc[1]["SKU"] == "test-product-456"


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,decimal_places,expected",
    [
        (5.2, 2, "5,20"),
        (299.99, 2, "299,99"),
        (0.0, 2, "0,00"),
        (1234.56, 2, "1234,56"),
        (0.1, 2, "0,10"),
        (999.999, 2, "1000,00"),  # Rounding
        (5.2, 1, "5,2"),
        (299.99, 3, "299,990"),
        (None, 2, ""),  # None returns empty string
    ],
)
def test_format_german_decimal(value, decimal_places, expected):
    """Test German decimal formatting with comma separator."""
    result = format_german_decimal(value, decimal_places)
    assert result == expected


@pytest.mark.unit
def test_format_german_decimal_default_places():
    """Test German decimal formatting uses 2 decimal places by default."""
    result = format_german_decimal(10.5)
    assert result == "10,50"


@pytest.mark.unit
def test_format_german_decimal_none_returns_empty():
    """Test German decimal formatting returns empty string for None."""
    result = format_german_decimal(None)
    assert result == ""


@pytest.mark.unit
def test_map_woocommerce_attributes_uses_german_names():
    """Test attribute mapping uses standardized German attribute names."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
    )

    result = _map_woocommerce_attributes(product)

    assert result["Attribut 1 Name"] == "Farbe"
    assert result["Attribut 2 Name"] == "Lichtfarbe"
    assert result["Attribut 3 Name"] == "Dimmbarkeit"
    assert result["Attribut 4 Name"] == "Montage"


@pytest.mark.unit
def test_map_woocommerce_attributes_simple_product_visibility():
    """Test attribute visibility for simple products."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
        product_type="simple",
    )

    result = _map_woocommerce_attributes(product)

    # Simple products should have visible attributes
    assert result["Attribut 1 Sichtbar"] == 1
    assert result["Attribut 2 Sichtbar"] == 1


@pytest.mark.unit
def test_map_woocommerce_attributes_variation_visibility():
    """Test attribute visibility for variation products."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
        product_type="variation",
    )

    result = _map_woocommerce_attributes(product)

    # Variations should have empty/hidden attributes
    assert result["Attribut 1 Sichtbar"] == ""
    assert result["Attribut 2 Sichtbar"] == ""


@pytest.mark.unit
def test_map_woocommerce_attributes_always_global():
    """Test all attributes are marked as global."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
    )

    result = _map_woocommerce_attributes(product)

    # All attributes should be global (empty string for unused attributes)
    assert result["Attribut 1 Global"] == ""
    assert result["Attribut 2 Global"] == ""
    assert result["Attribut 3 Global"] == ""
    assert result["Attribut 4 Global"] == ""


@pytest.mark.unit
def test_export_variable_product_to_csv():
    """Test export of variable product with variations."""
    # Create parent product
    parent = ProductData(
        sku=SKU(""),  # Empty SKU for parent
        name="Kelly Pendant Light",
        description="Beautiful pendant light with variations",
        manufacturer=Manufacturer("lodes"),
        categories=["Pendant"],
        attributes={"Designer": "Andrea Tosetto"},
        images=[ImageUrl("https://example.com/kelly.jpg")],
        product_type="variable",
        variation_attributes={
            "Farbe": "Black, White",
            "Lichtfarbe": "2700K, 3000K",
        },
    )

    # Create variations
    child1 = ProductData(
        sku=SKU("KELLY-BLACK-2700K"),
        name="Kelly - Black 2700K",
        description="",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
        product_type="variation",
        parent_sku=SKU(""),  # Parent has empty SKU
        variation_attributes={"Farbe": "Black", "Lichtfarbe": "2700K"},
    )

    child2 = ProductData(
        sku=SKU("KELLY-WHITE-3000K"),
        name="Kelly - White 3000K",
        description="",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
        product_type="variation",
        parent_sku=SKU(""),
        variation_attributes={"Farbe": "White", "Lichtfarbe": "3000K"},
    )

    products = [parent, child1, child2]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_variable.csv"
        export_to_woocommerce_csv(products, output_path)

        df = pd.read_csv(
            output_path, encoding="utf-8-sig", sep=";", keep_default_na=False
        )

        # Should have 3 rows: 1 parent + 2 variations
        assert len(df) == 3

        # Check parent product (row 0)
        parent_row = df.iloc[0]
        assert parent_row["ID"] == ""  # Empty - WooCommerce assigns IDs during import
        assert parent_row["Typ"] == "variable"
        assert parent_row["SKU"] == ""  # Empty SKU for parent
        assert parent_row["Attribut 1 Name"] == "Farbe"
        # Colors are translated to German
        assert parent_row["Attribut 1 Wert(e)"] == "Schwarz, Weiß"
        assert int(parent_row["Attribut 1 Sichtbar"]) == 1  # Visible for parent
        assert parent_row["Attribut 1 Global"] == ""  # Empty for attributes
        assert parent_row["Attribut 2 Name"] == "Lichtfarbe"
        assert parent_row["Attribut 2 Wert(e)"] == "2700K, 3000K"
        assert (
            int(parent_row["Kundenrezensionen erlauben?"]) == 1
        )  # Reviews allowed for parent

        # Check first child variation (row 1)
        child1_row = df.iloc[1]
        assert child1_row["ID"] == ""  # Empty - WooCommerce assigns IDs during import
        assert child1_row["Typ"] == "variation"
        assert child1_row["SKU"] == "KELLY-BLACK-2700K"
        assert child1_row["Parent SKU"] == ""  # Parent's SKU (empty for parent)
        assert child1_row["Attribut 1 Name"] == "Farbe"
        # Colors are translated to German
        assert child1_row["Attribut 1 Wert(e)"] == "Schwarz"
        assert child1_row["Attribut 1 Sichtbar"] == ""  # Empty for variations
        assert child1_row["Attribut 1 Global"] == ""  # Empty for attributes
        assert (
            int(child1_row["Kundenrezensionen erlauben?"]) == 0
        )  # No reviews for variations

        # Check second child variation (row 2)
        child2_row = df.iloc[2]
        assert child2_row["ID"] == ""  # Empty - WooCommerce assigns IDs during import
        assert child2_row["Typ"] == "variation"
        assert child2_row["SKU"] == "KELLY-WHITE-3000K"
        assert child2_row["Parent SKU"] == ""  # Parent's SKU (empty for parent)
        assert child2_row["Attribut 1 Name"] == "Farbe"
        # Colors are translated to German
        assert child2_row["Attribut 1 Wert(e)"] == "Weiß"


@pytest.mark.unit
class TestBuildShortDescriptionHtml:
    """Test HTML short description generation."""

    def test_builds_html_with_all_specs(self):
        """Test short description HTML includes all available specs."""
        product = ProductData(
            sku=SKU("test"),
            name="Kelly Pendant Light",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            installation_type="Hängeleuchte",
            material="Aluminum",
            light_specs={"wattage": "25", "kelvin": "2700K", "lumen": "2000"},
            dimensions={"length": 50.0, "width": 30.0, "height": 20.0},
            variation_attributes={"Farbe": "Black"},
        )

        result = build_short_description_html(product)

        # Check opening line
        assert "Hängeleuchte - Kelly Pendant Light" in result

        # Check HTML structure
        assert "<ul>" in result
        assert "</ul>" in result
        assert "<li><strong>Lichttechnik:</strong>" in result
        assert "<li><strong>Material:</strong>" in result
        assert "<li><strong>Farbe:</strong>" in result
        assert "<li><strong>Abmessungen:</strong>" in result

        # Check values
        assert "LED 25W" in result
        assert "2700K" in result
        assert "2000lm" in result
        assert "Aluminum" in result
        # Colors are translated to German
        assert "Schwarz" in result
        assert "50.0x30.0x20.0cm" in result

    def test_builds_html_with_partial_specs(self):
        """Test short description HTML with only some specs available."""
        product = ProductData(
            sku=SKU("test"),
            name="Test Light",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            material="Steel",
            light_specs={"kelvin": "3000K"},
        )

        result = build_short_description_html(product)

        assert "<li><strong>Lichttechnik:</strong> 3000K</li>" in result
        assert "<li><strong>Material:</strong> Steel</li>" in result

    def test_returns_plain_text_when_no_specs(self):
        """Test short description returns plain intro when no specs available."""
        product = ProductData(
            sku=SKU("test"),
            name="Simple Light",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            installation_type="Wandleuchte",
        )

        result = build_short_description_html(product)

        # Should return just the intro without HTML list
        assert result == "Wandleuchte - Simple Light"
        assert "<ul>" not in result

    def test_handles_missing_installation_type(self):
        """Test short description when installation type is missing."""
        product = ProductData(
            sku=SKU("test"),
            name="Test Light",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            material="Glass",
        )

        result = build_short_description_html(product)

        # Should use just the name
        assert "Test Light" in result
        assert "<li><strong>Material:</strong> Glass</li>" in result


@pytest.mark.unit
def test_woocommerce_csv_uses_semicolon_separator(sample_product):
    """Test CSV uses semicolon separator instead of comma."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        # Read raw file content
        with open(output_path, "r", encoding="utf-8-sig") as f:
            first_line = f.readline()

        # Should contain semicolons
        assert ";" in first_line
        # Header should start with "ID;Typ;SKU"
        assert first_line.startswith("ID;Typ;SKU")


@pytest.mark.unit
def test_woocommerce_csv_contains_new_custom_columns(sample_product):
    """Test CSV contains all new custom columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path, encoding="utf-8-sig", sep=";")

        new_columns = [
            "SKU",
            "Parent SKU",
            "Lieferzeit",
            "Übergkategorie",
            "Kategorienstruktur",
            "Anzahl Fotos",
            "Produktnummer",
            "Produkttyp",
            "Designer",
            "Produktfamilie",
            "Material",
            "Diffusor",
            "Produktfarben",
            "Seillänge",
            "Lichtquelle",
            "Dimmbarkeit",
            "IP-Schutz",
            "Stoßfestigkeit",
            "Spannung",
            "Zertifizierung",
            "Information",
            "Datenblatt",
            "Montageanleitung",
        ]

        for col in new_columns:
            assert col in df.columns, f"Missing new column: {col}"


@pytest.mark.unit
def test_variation_names_use_space_separator():
    """Test variation names use space instead of dash separator."""
    # Create parent product
    parent = ProductData(
        sku=SKU("14126"),
        name="Kelly small dome 50",
        description="Beautiful pendant light",
        manufacturer=Manufacturer("lodes"),
        categories=["Pendant"],
        attributes={"Designer": "Andrea Tosetto"},
        images=[ImageUrl("https://example.com/kelly.jpg")],
        product_type="variable",
        variation_attributes={"Farbe": "Weiß, Schwarz"},
    )

    # Create variation with space separator (not " - ")
    child = ProductData(
        sku=SKU("14126 1000"),
        name="Kelly small dome 50 Weiß",  # Space separator
        description="",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
        product_type="variation",
        parent_sku=SKU("14126"),
        variation_attributes={"Farbe": "Weiß"},
    )

    products = [parent, child]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/test_variable.csv"
        export_to_woocommerce_csv(products, output_path)

        df = pd.read_csv(output_path, encoding="utf-8-sig", sep=";")
        child_row = df.iloc[1]

        # Should NOT contain " - " separator
        assert " - " not in child_row["Name"]
        # Should contain the color with space separator
        assert child_row["Name"] == "Kelly small dome 50 Weiß"


@pytest.mark.unit
@pytest.mark.parametrize(
    "input_text,expected",
    [
        # Basic translation without whitespace issues
        ("Bianco Opaco – 9010", "Weiß Matt"),
        ("Nero Opaco – 9005", "Schwarz Matt"),
        ("Bronzo Ramato", "Bronze"),
        ("Champagne Opaco", "Champagner Matt"),
        # Whitespace collapsing (critical fix)
        ("Weiß\n\t\tMatt", "Weiß Matt"),
        ("Weiß  \n  Matt", "Weiß Matt"),
        ("  Weiß Matt  ", "Weiß Matt"),
        ("Bianco Opaco\n\t\t\t– 9010", "Weiß Matt"),
        # Multiple colors with excessive whitespace
        (
            "Bianco Opaco – 9010\n\t\t\t\t\tNero Opaco – 9005",
            "Weiß Matt Schwarz Matt",
        ),
        # Already clean (no change needed)
        ("Weiß Matt", "Weiß Matt"),
        ("Schwarz Matt", "Schwarz Matt"),
    ],
)
def test_translate_colors_to_german(input_text, expected):
    """Should translate Italian/English colors to German and collapse whitespace.

    This test covers the critical fix for excessive whitespace (newlines, tabs)
    that was causing CSV parsing issues in the Produktfarben field.
    """
    result = translate_colors_to_german(input_text)
    assert result == expected


@pytest.mark.unit
def test_translate_colors_to_german_removes_color_codes():
    """Should remove color codes like '– 9010' from color names."""
    assert translate_colors_to_german("Bianco Opaco – 9010") == "Weiß Matt"
    assert translate_colors_to_german("Nero Opaco – 9005") == "Schwarz Matt"
    assert translate_colors_to_german("Bianco - 1234") == "Weiß"


@pytest.mark.unit
def test_translate_colors_to_german_handles_mixed_languages():
    """Should handle Italian, English, and already-German color names."""
    # Italian
    assert "Weiß" in translate_colors_to_german("Bianco Opaco")
    # English
    assert "Weiß" in translate_colors_to_german("White")
    # Already German
    assert translate_colors_to_german("Weiß Matt") == "Weiß Matt"


# Import new functions to test
from src.exporters.woocommerce_csv import (
    extract_clean_product_name,
    build_short_description_plain,
)


@pytest.mark.unit
class TestExtractCleanProductName:
    """Test clean product name extraction without design attribution."""

    @pytest.mark.parametrize(
        "product_name,expected_clean_name",
        [
            # With design attribution
            ("Kelly, Design von Andrea Tosetto, 2015", "Kelly"),
            ("Kelly, design von Andrea Tosetto", "Kelly"),
            ("Kelly, Designer Andrea Tosetto", "Kelly"),
            ("A-Tube, Design by John Doe", "A-Tube"),
            # Without design attribution
            ("Kelly small dome 50", "Kelly small dome 50"),
            ("Kelly small dome 50 Weiß", "Kelly small dome 50 Weiß"),
            ("Simple Product Name", "Simple Product Name"),
            # Edge cases
            ("Kelly, Large", "Kelly, Large"),  # Comma but no "design" keyword
            ("Product, Something, Else", "Product, Something, Else"),  # Multiple commas
            ("", ""),  # Empty string
        ],
    )
    def test_extract_clean_name_from_various_formats(
        self, product_name: str, expected_clean_name: str
    ):
        """Should extract clean name and remove design attribution."""
        product = ProductData(
            sku=SKU("test-sku"),
            name=product_name,
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
        )

        result = extract_clean_product_name(product)

        assert result == expected_clean_name

    def test_extract_clean_name_handles_none_name(self):
        """Should return empty string when product name is None."""
        product = ProductData(
            sku=SKU("test-sku"),
            name="",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
        )

        result = extract_clean_product_name(product)

        assert result == ""

    def test_extract_clean_name_case_insensitive(self):
        """Should handle different cases of 'Design' keyword."""
        test_cases = [
            ("Kelly, DESIGN von Andrea", "Kelly"),
            ("Kelly, Design VON Andrea", "Kelly"),
            ("Kelly, designer Andrea", "Kelly"),
            ("Kelly, DESIGNER Andrea", "Kelly"),
        ]

        for product_name, expected in test_cases:
            product = ProductData(
                sku=SKU("test-sku"),
                name=product_name,
                description="Test",
                manufacturer=Manufacturer("lodes"),
                categories=[],
                attributes={},
                images=[],
            )
            result = extract_clean_product_name(product)
            assert result == expected, f"Failed for: {product_name}"


@pytest.mark.unit
class TestBuildShortDescriptionPlain:
    """Test plain text short description building."""

    def test_uses_ai_generated_description_when_available(self):
        """Should use AI-generated short_description if available."""
        product = ProductData(
            sku=SKU("14126"),
            name="Kelly",
            description="Test description",
            manufacturer=Manufacturer("lodes"),
            categories=["Ceiling"],
            attributes={},
            images=[],
            product_type="variable",
            available_colors="Weiß, Schwarz",
            short_description="Die Kelly Leuchte ist ein modernes Designstück.",
        )

        result = build_short_description_plain(product)

        assert result == "Die Kelly Leuchte ist ein modernes Designstück."

    def test_returns_empty_for_variation_products(self):
        """Should return empty string for variation products."""
        product = ProductData(
            sku=SKU("14126-1000"),
            name="Kelly Weiß",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            product_type="variation",
            parent_sku=SKU("14126"),
            short_description="Some description",
        )

        result = build_short_description_plain(product)

        assert result == ""

    def test_fallback_with_installation_type_and_family_name(self):
        """Should fall back to generic format when no AI description."""
        product = ProductData(
            sku=SKU("test-sku"),
            name="Test Product Family",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=["Ceiling"],
            attributes={},
            images=[],
            product_type="simple",
            installation_type="Hängeleuchte",
            short_description=None,  # No AI description
        )

        result = build_short_description_plain(product)

        # extract_product_family returns first word only
        assert result == "Hängeleuchte - Test"

    def test_fallback_with_only_installation_type(self):
        """Should use installation type when family name not extractable."""
        product = ProductData(
            sku=SKU("test-sku"),
            name="Test, Design von Someone",  # Will be stripped
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            product_type="simple",
            installation_type="Wandleuchte",
            short_description=None,
        )

        result = build_short_description_plain(product)

        # Should extract "Test" as family name
        assert "Wandleuchte" in result
        assert "Test" in result

    def test_fallback_returns_empty_when_no_data_available(self):
        """Should return empty string when no description or fallback data."""
        product = ProductData(
            sku=SKU("test-sku"),
            name="",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            product_type="simple",
            installation_type=None,
            short_description=None,
        )

        result = build_short_description_plain(product)

        assert result == ""

    @pytest.mark.parametrize(
        "product_type,has_short_desc,expected_empty",
        [
            ("variation", True, True),  # Variations always empty
            ("variation", False, True),
            ("variable", True, False),  # Variable uses short_desc
            ("simple", True, False),  # Simple uses short_desc
        ],
    )
    def test_handles_different_product_types(
        self, product_type: str, has_short_desc: bool, expected_empty: bool
    ):
        """Should handle different product types appropriately."""
        product = ProductData(
            sku=SKU("test-sku"),
            name="Test Product",
            description="Test",
            manufacturer=Manufacturer("lodes"),
            categories=[],
            attributes={},
            images=[],
            product_type=product_type,
            short_description="AI generated description" if has_short_desc else None,
            parent_sku=SKU("parent-sku") if product_type == "variation" else None,
        )

        result = build_short_description_plain(product)

        if expected_empty:
            assert result == ""
        else:
            assert result != ""


@pytest.mark.integration
class TestWooCommerceCsvKurzbeschreibung:
    """Integration tests for Kurzbeschreibung field in WooCommerce CSV export."""

    def test_parent_product_has_plain_text_kurzbeschreibung(self, tmp_path):
        """Should export parent product with plain text Kurzbeschreibung (no HTML)."""
        parent = ProductData(
            sku=SKU("parent-sku"),
            name="Kelly, Design von Andrea Tosetto, 2015",
            description="Full description",
            manufacturer=Manufacturer("lodes"),
            categories=["Ceiling"],
            attributes={"Material": "Aluminum"},
            images=[ImageUrl("https://example.com/image.jpg")],
            product_type="variable",
            available_colors="Weiß, Schwarz",
            short_description="Die Kelly Leuchte besticht durch modernes Design.",
            regular_price=500.0,
        )

        variation = ProductData(
            sku=SKU("parent-sku-1000"),
            name="Kelly Weiß",
            description="Variation description",
            manufacturer=Manufacturer("lodes"),
            categories=["Ceiling"],
            attributes={"Material": "Aluminum"},
            images=[ImageUrl("https://example.com/image.jpg")],
            product_type="variation",
            parent_sku=SKU("parent-sku"),
            variation_attributes={"Farbe": "Weiß"},
            short_description="Should be ignored",
            regular_price=500.0,
        )

        # Export to CSV
        output_file = tmp_path / "test_output.csv"
        export_to_woocommerce_csv([parent, variation], str(output_file))

        # Read and verify
        df = pd.read_csv(output_file, sep=";", encoding="utf-8-sig")

        # Parent product (row 0)
        parent_row = df.iloc[0]
        assert parent_row["Typ"] == "variable"
        assert parent_row["Name"] == "Kelly"  # No design attribution
        assert (
            parent_row["Kurzbeschreibung"]
            == "Die Kelly Leuchte besticht durch modernes Design."
        )
        assert "<" not in parent_row["Kurzbeschreibung"]  # No HTML tags
        assert ">" not in parent_row["Kurzbeschreibung"]

        # Variation product (row 1)
        variation_row = df.iloc[1]
        assert variation_row["Typ"] == "variation"
        assert variation_row["Name"] == "Kelly Weiß"  # Variation name preserved
        assert (
            pd.isna(variation_row["Kurzbeschreibung"])
            or variation_row["Kurzbeschreibung"] == ""
        )

    def test_fallback_kurzbeschreibung_when_no_ai_description(self, tmp_path):
        """Should fall back to generic format when no AI-generated description."""
        product = ProductData(
            sku=SKU("test-sku"),
            name="Test Product Name",
            description="Full description",
            manufacturer=Manufacturer("lodes"),
            categories=["Ceiling"],
            attributes={},
            images=[],
            product_type="simple",
            installation_type="Hängeleuchte",
            short_description=None,  # No AI description
            regular_price=300.0,
        )

        # Export to CSV
        output_file = tmp_path / "test_fallback.csv"
        export_to_woocommerce_csv([product], str(output_file))

        # Read and verify
        df = pd.read_csv(output_file, sep=";", encoding="utf-8-sig")

        row = df.iloc[0]
        # extract_product_family returns first word only ("Test" from "Test Product Name")
        assert row["Kurzbeschreibung"] == "Hängeleuchte - Test"
        assert "<" not in row["Kurzbeschreibung"]  # No HTML tags

    def test_name_field_removes_design_attribution(self, tmp_path):
        """Should export clean product names without design attribution."""
        products = [
            ProductData(
                sku=SKU("sku-1"),
                name="Kelly, Design von Andrea Tosetto, 2015",
                description="Test",
                manufacturer=Manufacturer("lodes"),
                categories=[],
                attributes={},
                images=[],
                regular_price=100.0,
            ),
            ProductData(
                sku=SKU("sku-2"),
                name="A-Tube, Designer John Doe",
                description="Test",
                manufacturer=Manufacturer("lodes"),
                categories=[],
                attributes={},
                images=[],
                regular_price=200.0,
            ),
            ProductData(
                sku=SKU("sku-3"),
                name="Simple Product Name",
                description="Test",
                manufacturer=Manufacturer("lodes"),
                categories=[],
                attributes={},
                images=[],
                regular_price=150.0,
            ),
        ]

        # Export to CSV
        output_file = tmp_path / "test_names.csv"
        export_to_woocommerce_csv(products, str(output_file))

        # Read and verify
        df = pd.read_csv(output_file, sep=";", encoding="utf-8-sig")

        assert df.iloc[0]["Name"] == "Kelly"
        assert df.iloc[1]["Name"] == "A-Tube"
        assert df.iloc[2]["Name"] == "Simple Product Name"

        # Ensure no design attribution in any name
        for _, row in df.iterrows():
            assert "Design" not in row["Name"]
            assert "Designer" not in row["Name"]
