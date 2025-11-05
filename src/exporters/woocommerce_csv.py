"""WooCommerce CSV exporter.

Following CLAUDE.md: pure, testable functions with clear responsibilities.
Based on official WooCommerce CSV import format specification.
"""

import csv
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from src.types import ProductData


def export_to_woocommerce_csv(
    products: list[ProductData], output_path: str = "output/products.csv"
) -> Path:
    """Export products to WooCommerce-compatible CSV format.

    Args:
        products: List of product data to export
        output_path: Path to output CSV file

    Returns:
        Path to created CSV file

    Raises:
        ValueError: If products list is empty
    """
    if not products:
        raise ValueError("Cannot export empty product list")

    # Build DataFrame with WooCommerce columns
    rows = [_product_to_woocommerce_row(product) for product in products]
    df = pd.DataFrame(rows)

    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Export to CSV with proper encoding
    df.to_csv(output_file, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)

    logger.info(f"Exported {len(products)} products to {output_file}")
    return output_file


def _product_to_woocommerce_row(product: ProductData) -> dict[str, Any]:
    """Convert ProductData to WooCommerce CSV row format.

    Args:
        product: Product data to convert

    Returns:
        Dictionary representing a CSV row with WooCommerce columns
    """
    # Format images: pipe-separated URLs (first image becomes featured)
    images = "|".join(product.images) if product.images else ""

    # Format categories: comma-separated
    categories = ", ".join(product.categories) if product.categories else "Lighting"

    # Base WooCommerce columns
    row = {
        "ID": "",  # Empty for new products
        "Type": product.product_type,  # simple, variable, or variation
        "SKU": product.sku,
        "Name": product.name,
        "Published": 1,  # 1 = published
        "Is featured?": 0,  # 0 = not featured
        "Visibility in catalog": "visible",
        "Short description": _truncate_description(product.description, 120),
        "Description": product.description,
        "Date sale price starts": "",
        "Date sale price ends": "",
        "Tax status": "taxable",
        "Tax class": "",
        "In stock?": 1,
        "Stock": product.stock if product.stock is not None else "",
        "Low stock amount": "",
        "Backorders allowed?": 0,
        "Sold individually?": 0,
        "Weight": product.weight if product.weight is not None else "",
        "Length": "",
        "Width": "",
        "Height": "",
        "Allow customer reviews?": 1,
        "Purchase note": "",
        "Sale price": product.sale_price if product.sale_price is not None else "",
        "Regular price": (
            product.regular_price if product.regular_price is not None else ""
        ),
        "Categories": categories,
        "Tags": product.manufacturer,  # Use manufacturer as tag
        "Shipping class": "",
        "Images": images,
        "Download limit": "",
        "Download expiry days": "",
        "Parent": product.parent_sku if product.parent_sku else "",
        "Grouped products": "",
        "Upsells": "",
        "Cross-sells": "",
        "External URL": "",
        "Button text": "",
        "Position": 0,
    }

    # Add variation attributes for variable/variation products
    if product.variation_attributes:
        for idx, (attr_name, attr_value) in enumerate(
            product.variation_attributes.items(), start=1
        ):
            row[f"Attribute {idx} name"] = attr_name
            row[f"Attribute {idx} value(s)"] = attr_value
            row[f"Attribute {idx} visible"] = 1
            row[f"Attribute {idx} global"] = 0

    # Add custom attributes as meta fields
    if product.attributes:
        for key, value in product.attributes.items():
            # Sanitize key for meta field (replace spaces with underscores)
            meta_key = f"meta:{_sanitize_meta_key(key)}"
            row[meta_key] = value

    # Add EAN if available
    if product.ean:
        row["meta:EAN"] = product.ean

    # Add dimensions if available
    if product.dimensions:
        if "length" in product.dimensions:
            row["Length"] = product.dimensions["length"]
        if "width" in product.dimensions:
            row["Width"] = product.dimensions["width"]
        if "height" in product.dimensions:
            row["Height"] = product.dimensions["height"]

    return row


def _truncate_description(text: str, max_length: int) -> str:
    """Truncate description to max length, adding ellipsis if needed.

    Args:
        text: Text to truncate
        max_length: Maximum character length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - 3].strip() + "..."


def _sanitize_meta_key(key: str) -> str:
    """Sanitize attribute key for WooCommerce meta field.

    Args:
        key: Original attribute key

    Returns:
        Sanitized key suitable for meta field name
    """
    # Replace spaces and special characters with underscores
    sanitized = key.replace(" ", "_").replace("-", "_").replace("/", "_")
    # Remove any remaining special characters
    sanitized = "".join(c for c in sanitized if c.isalnum() or c == "_")
    return sanitized.lower()
