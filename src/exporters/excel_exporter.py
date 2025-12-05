"""Excel XLSX exporter for product data.

Following CLAUDE.md: pure, testable functions with clear responsibilities.
"""

from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from src.models import ProductData


def export_to_excel(
    products: list[ProductData], output_path: str = "output/products.xlsx"
) -> Path:
    """Export products to Excel XLSX format.

    Args:
        products: List of product data to export
        output_path: Path to output XLSX file

    Returns:
        Path to created XLSX file

    Raises:
        ValueError: If products list is empty
    """
    if not products:
        raise ValueError("Cannot export empty product list")

    # Build DataFrame with clean column structure
    rows = [_product_to_excel_row(product) for product in products]
    df = pd.DataFrame(rows)

    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Export to Excel with formatting
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Products", index=False)

        # Auto-adjust column widths
        worksheet = writer.sheets["Products"]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter

            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass

            adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
            worksheet.column_dimensions[column_letter].width = adjusted_width

    logger.info(f"Exported {len(products)} products to {output_file}")
    return output_file


def _product_to_excel_row(product: ProductData) -> dict[str, Any]:
    """Convert ProductData to Excel row format.

    Args:
        product: Product data to convert

    Returns:
        Dictionary representing an Excel row
    """
    row = {
        "SKU": product.sku,
        "Name": product.name,
        "Manufacturer": product.manufacturer,
        "Description": product.description,
        "Categories": ", ".join(product.categories) if product.categories else "",
        "Regular Price": product.regular_price if product.regular_price else "",
        "Sale Price": product.sale_price if product.sale_price else "",
        "Stock": product.stock if product.stock else "",
        "Weight": product.weight if product.weight else "",
        "EAN": product.ean if product.ean else "",
        "Image URLs": "\n".join(product.images) if product.images else "",
        "Image Count": len(product.images),
    }

    # Add dimensions if available
    if product.dimensions:
        row["Length"] = product.dimensions.get("length", "")
        row["Width"] = product.dimensions.get("width", "")
        row["Height"] = product.dimensions.get("height", "")

    # Add attributes as separate columns
    if product.attributes:
        for key, value in product.attributes.items():
            row[f"Attr: {key}"] = value

    return row
