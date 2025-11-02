"""Unit tests for exporters.

Following CLAUDE.md: parameterized inputs, test entire structure, no trivial asserts.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.types import ProductData, SKU, ImageUrl, Manufacturer
from src.exporters.woocommerce_csv import export_to_woocommerce_csv
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
    """Should include all required WooCommerce columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)

        # Check required columns exist
        required_columns = ["SKU", "Name", "Type", "Published", "Description", "Images"]
        for col in required_columns:
            assert col in df.columns, f"Missing required column: {col}"


@pytest.mark.unit
def test_woocommerce_csv_product_data_accuracy(sample_product):
    """Should accurately export product data to CSV."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)
        row = df.iloc[0]

        assert row["SKU"] == "test-product-123"
        assert row["Name"] == "Test Ceiling Light"
        assert row["Type"] == "simple"
        assert row["Published"] == 1
        assert "beautiful test ceiling light" in row["Description"].lower()
        assert "Ceiling, Modern" in row["Categories"]
        assert row["Regular price"] == 299.99
        assert row["Stock"] == 10


@pytest.mark.unit
def test_woocommerce_csv_images_pipe_separated(sample_product):
    """Should format images as pipe-separated URLs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = f"{tmpdir}/products.csv"
        export_to_woocommerce_csv([sample_product], output_path)

        df = pd.read_csv(output_path)
        images = df.iloc[0]["Images"]

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

        # Verify CSV
        csv_df = pd.read_csv(csv_path)
        assert len(csv_df) == 2
        assert list(csv_df["SKU"]) == ["test-product-123", "test-product-456"]

        # Verify Excel
        excel_df = pd.read_excel(excel_path, sheet_name="Products")
        assert len(excel_df) == 2
        assert list(excel_df["Name"]) == ["Test Ceiling Light", "Test Wall Sconce"]
