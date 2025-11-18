"""Unit tests for exporters.

Following CLAUDE.md: parameterized inputs, test entire structure, no trivial asserts.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.types import ProductData, SKU, ImageUrl, Manufacturer
from src.exporters.woocommerce_csv import (
    export_to_woocommerce_csv,
    format_german_decimal,
    _map_product_attributes_to_woocommerce,
    _map_variation_attributes_to_woocommerce,
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
            name="Test Wall Sconce",
            description="Elegant wall-mounted lighting.",
            manufacturer=Manufacturer("lodes"),
            categories=["Wall", "Classic"],
            attributes={"Designer": "Another Designer"},
            images=[ImageUrl("https://example.com/image3.jpg")],
            regular_price=199.99,
        ),
    ]


@pytest.mark.unit
def test_export_to_woocommerce_csv_creates_file(sample_product):
    """Should create CSV file with correct structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"

        result_path = export_to_woocommerce_csv([sample_product], output_path)

        assert result_path.exists()
        assert result_path == Path(output_path)


@pytest.mark.unit
def test_woocommerce_csv_contains_correct_columns(sample_product):
    """Should include all required WooCommerce columns (German)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)

        # Check required German columns exist
        required_columns = [
            "Artikelnummer",  # SKU
            "Name",  # Name (same in German)
            "Typ",  # Type
            "Veröffentlicht",  # Published
            "Beschreibung",  # Description
            "Bilder",  # Images
            "Marken",  # Brands (new field)
        ]
        for col in required_columns:
            assert col in df.columns, f"Missing required column: {col}"


@pytest.mark.unit
def test_woocommerce_csv_product_data_accuracy(sample_product):
    """Should accurately export product data to CSV with German columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)
        row = df.iloc[0]

        # Check German column names
        assert row["Artikelnummer"] == "test-product-123"  # SKU
        assert row["Name"] == "Test Ceiling Light"
        assert row["Typ"] == "simple"  # Type
        assert row["Veröffentlicht"] == 1  # Published
        assert (
            "beautiful test ceiling light" in row["Beschreibung"].lower()
        )  # Description
        assert "Ceiling, Modern" in row["Kategorien"]  # Categories
        # Check German decimal formatting (comma separator)
        assert row["Regulärer Preis"] == "299,99"  # Regular price with comma
        assert row["Bestand"] == 10  # Stock


@pytest.mark.unit
def test_woocommerce_csv_images_pipe_separated(sample_product):
    """Should format images as pipe-separated URLs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)
        images = df.iloc[0]["Bilder"]  # German column name for Images

        assert "|" in images
        assert "image1.jpg" in images
        assert "image2.jpg" in images


@pytest.mark.unit
def test_woocommerce_csv_attributes_mapped_to_standard_columns(sample_product):
    """Should map custom attributes to WooCommerce Attribut 1-4 columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)
        row = df.iloc[0]

        # Check attributes are in Attribut columns, not meta: columns
        assert "Attribut 1 Name" in df.columns
        assert row["Attribut 1 Name"] == "Designer"
        assert row["Attribut 1 Wert(e)"] == "Test Designer"
        assert row["Attribut 1 Sichtbar"] == 1
        assert row["Attribut 1 Global"] == 0


@pytest.mark.unit
def test_woocommerce_csv_all_columns_present(sample_product):
    """Should include all WooCommerce columns even if empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)

        # Check all attribute columns are present
        for i in range(1, 5):
            assert f"Attribut {i} Name" in df.columns
            assert f"Attribut {i} Wert(e)" in df.columns
            assert f"Attribut {i} Sichtbar" in df.columns
            assert f"Attribut {i} Global" in df.columns

        # Check standard columns are present
        for i in [1, 2, 3, 4]:
            assert f"Attribut {i} Standard" in df.columns


@pytest.mark.unit
def test_woocommerce_csv_no_meta_columns(sample_product):
    """Should not include meta: columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)

        # Verify no meta: columns exist
        meta_columns = [col for col in df.columns if col.startswith("meta:")]
        assert len(meta_columns) == 0


@pytest.mark.unit
def test_woocommerce_csv_format_matches_schema():
    """Should use QUOTE_MINIMAL and LF line endings."""
    product = ProductData(
        sku=SKU("test-123"),
        name="Test Product",
        description="Test description",
        manufacturer=Manufacturer("lodes"),
        categories=["Test"],
        attributes={"Designer": "Test Designer"},
        images=[],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([product], output_path)

        # Read raw file content
        with open(output_path, "rb") as f:
            content = f.read()

        # Check for LF line endings (not CRLF)
        assert b"\r\n" not in content, "Should use LF not CRLF"
        assert b"\n" in content

        # Check that simple values are not quoted (QUOTE_MINIMAL behavior)
        content_str = content.decode("utf-8-sig")
        lines = content_str.split("\n")

        # Header line should have some unquoted simple column names
        # (though columns with commas like "GTIN, UPC, EAN oder ISBN" will be quoted)
        assert "Typ" in lines[0] or '"Typ"' in lines[0]


@pytest.mark.unit
def test_woocommerce_csv_empty_list_raises_error():
    """Should raise ValueError when given empty product list."""
    with pytest.raises(ValueError, match="Cannot export empty product list"):
        export_to_woocommerce_csv([], "output.csv")


@pytest.mark.unit
def test_export_to_excel_creates_file(sample_product):
    """Should create Excel file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.xlsx"

        result_path = export_to_excel([sample_product], output_path)

        assert result_path.exists()
        assert result_path.suffix == ".xlsx"


@pytest.mark.unit
def test_excel_export_product_data_accuracy(sample_product):
    """Should accurately export product data to Excel."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.xlsx"
        export_to_excel([sample_product], output_path)

        df = pd.read_excel(output_path, sheet_name="Products")
        row = df.iloc[0]

        assert row["SKU"] == "test-product-123"
        assert row["Name"] == "Test Ceiling Light"
        assert row["Manufacturer"] == "lodes"
        assert row["Regular Price"] == 299.99
        assert row["Stock"] == 10
        assert row["Image Count"] == 2


@pytest.mark.unit
def test_excel_export_attributes_as_columns(sample_product):
    """Should export attributes as separate columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.xlsx"
        export_to_excel([sample_product], output_path)

        df = pd.read_excel(output_path, sheet_name="Products")

        assert "Attr: Designer" in df.columns
        assert df.iloc[0]["Attr: Designer"] == "Test Designer"
        assert df.iloc[0]["Attr: Material"] == "Aluminum"


@pytest.mark.unit
def test_excel_export_empty_list_raises_error():
    """Should raise ValueError when given empty product list."""
    with pytest.raises(ValueError, match="Cannot export empty product list"):
        export_to_excel([], "output.xlsx")


@pytest.mark.unit
def test_batch_export_multiple_products(multiple_products):
    """Should correctly export multiple products to both formats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = f"{tmpdir}/products.csv"
        excel_path = f"{tmpdir}/products.xlsx"

        export_to_woocommerce_csv(multiple_products, csv_path)
        export_to_excel(multiple_products, excel_path)

        # Verify CSV (German column names)
        csv_df = pd.read_csv(csv_path)
        assert len(csv_df) == 2
        assert list(csv_df["Artikelnummer"]) == [
            "test-product-123",
            "test-product-456",
        ]  # SKU

        # Verify Excel
        excel_df = pd.read_excel(excel_path, sheet_name="Products")
        assert len(excel_df) == 2
        assert list(excel_df["Name"]) == ["Test Ceiling Light", "Test Wall Sconce"]


# Test German decimal formatting function
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
    """Should format numbers with German decimal separator (comma)."""
    result = format_german_decimal(value, decimal_places)
    assert result == expected


@pytest.mark.unit
def test_format_german_decimal_default_places():
    """Should use 2 decimal places by default."""
    assert format_german_decimal(5.2) == "5,20"
    assert format_german_decimal(299.99) == "299,99"


@pytest.mark.unit
def test_format_german_decimal_none_returns_empty():
    """Should return empty string for None value."""
    result = format_german_decimal(None)
    assert result == ""
    assert isinstance(result, str)


# Tests for _map_product_attributes_to_woocommerce function
@pytest.mark.unit
def test_map_attributes_to_woocommerce_priority_order():
    """Should map attributes to Attribut 1-4 in priority order."""
    product = ProductData(
        sku=SKU("test"),
        name="Test Product",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={
            "Designer": "John Doe",
            "IP Rating": "IP65",
            "Voltage": "230V",
            "Certification": "CE",
        },
        images=[],
    )

    result = _map_product_attributes_to_woocommerce(product)

    assert result == {
        "Attribut 1 Name": "Designer",
        "Attribut 1 Wert(e)": "John Doe",
        "Attribut 1 Sichtbar": 1,
        "Attribut 1 Global": 0,
        "Attribut 2 Name": "IP Rating",
        "Attribut 2 Wert(e)": "IP65",
        "Attribut 2 Sichtbar": 1,
        "Attribut 2 Global": 0,
        "Attribut 3 Name": "Voltage",
        "Attribut 3 Wert(e)": "230V",
        "Attribut 3 Sichtbar": 1,
        "Attribut 3 Global": 0,
        "Attribut 4 Name": "Certification",
        "Attribut 4 Wert(e)": "CE",
        "Attribut 4 Sichtbar": 1,
        "Attribut 4 Global": 0,
    }


@pytest.mark.unit
def test_map_attributes_empty_dict_returns_empty():
    """Should return empty dict when product has no attributes."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
    )

    result = _map_product_attributes_to_woocommerce(product)

    assert result == {}


@pytest.mark.unit
def test_map_attributes_none_returns_empty():
    """Should return empty dict when attributes is None."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes=None,
        images=[],
    )

    result = _map_product_attributes_to_woocommerce(product)

    assert result == {}


@pytest.mark.unit
def test_map_attributes_more_than_four_takes_first_four():
    """Should only map first 4 attributes in priority order."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={
            "Designer": "Designer Name",
            "IP Rating": "IP65",
            "Voltage": "230V",
            "Certification": "CE",
            "Structure": "Metal",  # 5th - should be ignored
            "Diffusor": "Glass",  # 6th - should be ignored
        },
        images=[],
    )

    result = _map_product_attributes_to_woocommerce(product)

    # Should only have 4 attributes (16 keys: 4 attrs × 4 fields each)
    assert len(result) == 16
    assert "Attribut 4 Name" in result
    assert "Attribut 5 Name" not in result
    # Structure should not be included (it's 5th in priority)
    assert "Structure" not in result.values()


@pytest.mark.unit
def test_map_attributes_partial_priority_list():
    """Should map available attributes even if not all priority attrs exist."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={
            "Designer": "Designer Name",
            "Structure": "Metal",  # Lower priority
            "Random Attr": "Value",  # Not in priority list - should be ignored
        },
        images=[],
    )

    result = _map_product_attributes_to_woocommerce(product)

    # Should only map Designer (1st priority) and Structure (5th priority)
    assert len(result) == 8  # 2 attrs × 4 fields each
    assert result["Attribut 1 Name"] == "Designer"
    assert result["Attribut 2 Name"] == "Structure"
    assert "Random Attr" not in result.values()


@pytest.mark.unit
def test_map_attributes_sets_visibility_and_global():
    """Should set Sichtbar=1 and Global=0 for all attributes."""
    product = ProductData(
        sku=SKU("test"),
        name="Test",
        description="Test",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={"Designer": "Test"},
        images=[],
    )

    result = _map_product_attributes_to_woocommerce(product)

    assert result["Attribut 1 Sichtbar"] == 1
    assert result["Attribut 1 Global"] == 0


# Tests for _map_variation_attributes_to_woocommerce function
@pytest.mark.unit
def test_map_variation_attributes_to_woocommerce():
    """Should map variation attributes with Global=1."""
    variation_attrs = {"Structure": "Metal", "Diffusor": "Glass"}

    result = _map_variation_attributes_to_woocommerce(variation_attrs)

    assert result == {
        "Attribut 1 Name": "Structure",
        "Attribut 1 Wert(e)": "Metal",
        "Attribut 1 Sichtbar": 1,
        "Attribut 1 Global": 1,  # Global=1 for variations
        "Attribut 2 Name": "Diffusor",
        "Attribut 2 Wert(e)": "Glass",
        "Attribut 2 Sichtbar": 1,
        "Attribut 2 Global": 1,
    }


@pytest.mark.unit
def test_map_variation_attributes_sets_global_to_one():
    """Should set Global=1 for variation attributes (for WooCommerce filtering)."""
    variation_attrs = {"Structure": "Metal"}

    result = _map_variation_attributes_to_woocommerce(variation_attrs)

    assert result["Attribut 1 Global"] == 1  # Global attributes for variations


@pytest.mark.unit
def test_map_variation_attributes_empty_dict():
    """Should return empty dict when no variation attributes."""
    result = _map_variation_attributes_to_woocommerce({})

    assert result == {}


@pytest.mark.unit
def test_map_variation_attributes_none():
    """Should return empty dict when variation attributes is None."""
    result = _map_variation_attributes_to_woocommerce(None)

    assert result == {}


@pytest.mark.unit
def test_map_variation_attributes_max_four():
    """Should only map first 4 variation attributes."""
    variation_attrs = {
        "Attr1": "Val1",
        "Attr2": "Val2",
        "Attr3": "Val3",
        "Attr4": "Val4",
        "Attr5": "Val5",  # Should be ignored
    }

    result = _map_variation_attributes_to_woocommerce(variation_attrs)

    # Should only have 4 attributes (16 keys: 4 attrs × 4 fields each)
    assert len(result) == 16
    assert "Attribut 4 Name" in result
    assert "Attribut 5 Name" not in result


@pytest.mark.unit
def test_map_variation_attributes_comma_separated_values():
    """Should handle comma-separated values for parent variable products."""
    variation_attrs = {"Structure": "Metal, Wood, Aluminum"}

    result = _map_variation_attributes_to_woocommerce(variation_attrs)

    assert result["Attribut 1 Wert(e)"] == "Metal, Wood, Aluminum"


# Integration test for variable product CSV export
@pytest.mark.unit
def test_export_variable_product_to_csv():
    """Should export variable parent + variations with correct structure."""
    parent = ProductData(
        sku=SKU(""),  # Parent has no SKU
        name="Kelly Ceiling Light",
        description="Modern ceiling light",
        manufacturer=Manufacturer("lodes"),
        categories=["Ceiling", "Modern"],
        attributes={"Designer": "John Doe"},
        images=[ImageUrl("https://example.com/image.jpg")],
        product_type="variable",
        variation_attributes={"Structure": "Metal, Wood", "Diffusor": "Glass, Plastic"},
    )

    child1 = ProductData(
        sku=SKU("KELLY-METAL-GLASS"),
        name="Kelly Ceiling Light - Metal Glass",
        description="",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
        product_type="variation",
        parent_sku=SKU("kelly-base"),
        variation_attributes={"Structure": "Metal", "Diffusor": "Glass"},
    )

    child2 = ProductData(
        sku=SKU("KELLY-WOOD-PLASTIC"),
        name="Kelly Ceiling Light - Wood Plastic",
        description="",
        manufacturer=Manufacturer("lodes"),
        categories=[],
        attributes={},
        images=[],
        product_type="variation",
        parent_sku=SKU("kelly-base"),
        variation_attributes={"Structure": "Wood", "Diffusor": "Plastic"},
    )

    products = [parent, child1, child2]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/variable_products.csv"
        export_to_woocommerce_csv(products, output_path)

        # Read CSV preserving empty strings (not converting to NaN)
        df = pd.read_csv(output_path, keep_default_na=False)

        # Check we have 3 rows (parent + 2 children)
        assert len(df) == 3

        # Check parent product (row 0)
        parent_row = df.iloc[0]
        assert parent_row["Typ"] == "variable"
        assert parent_row["Artikelnummer"] == ""  # No SKU
        assert parent_row["Name"] == "Kelly Ceiling Light"
        assert parent_row["Attribut 1 Name"] == "Structure"
        assert parent_row["Attribut 1 Wert(e)"] == "Metal, Wood"
        assert parent_row["Attribut 1 Global"] == 1
        assert parent_row["Attribut 2 Name"] == "Diffusor"
        assert parent_row["Attribut 2 Wert(e)"] == "Glass, Plastic"
        assert parent_row["Attribut 2 Global"] == 1

        # Check first child variation (row 1)
        child1_row = df.iloc[1]
        assert child1_row["Typ"] == "variation"
        assert child1_row["Artikelnummer"] == "KELLY-METAL-GLASS"
        assert child1_row["Übergeordnetes Produkt"] == "id:kelly-base"
        assert child1_row["Attribut 1 Name"] == "Structure"
        assert child1_row["Attribut 1 Wert(e)"] == "Metal"
        assert child1_row["Attribut 1 Global"] == 1

        # Check second child variation (row 2)
        child2_row = df.iloc[2]
        assert child2_row["Typ"] == "variation"
        assert child2_row["Artikelnummer"] == "KELLY-WOOD-PLASTIC"
        assert child2_row["Übergeordnetes Produkt"] == "id:kelly-base"
        assert child2_row["Attribut 1 Name"] == "Structure"
        assert child2_row["Attribut 1 Wert(e)"] == "Wood"
