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
def test_woocommerce_csv_custom_attributes_as_meta(sample_product):
    """Should export custom attributes as meta fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)
        row = df.iloc[0]

        # Check meta fields exist
        assert "meta:designer" in df.columns
        assert row["meta:designer"] == "Test Designer"
        assert row["meta:material"] == "Aluminum"


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
