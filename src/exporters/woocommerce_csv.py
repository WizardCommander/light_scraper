"""WooCommerce CSV exporter.

Following CLAUDE.md: pure, testable functions with clear responsibilities.
Based on official WooCommerce CSV import format specification.
German column headers for German WooCommerce stores.
"""

import csv
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from src.types import ProductData


# WooCommerce German column names mapping (exact order from schema)
WOOCOMMERCE_GERMAN_COLUMNS = [
    "ID",
    "Typ",
    "Artikelnummer",
    "GTIN, UPC, EAN oder ISBN",
    "Name",
    "Veröffentlicht",
    "Ist hervorgehoben?",
    "Sichtbarkeit im Katalog",
    "Kurzbeschreibung",
    "Beschreibung",
    "Datum, an dem Angebotspreis beginnt",
    "Datum, an dem Angebotspreis endet",
    "Steuerstatus",
    "Steuerklasse",
    "Vorrätig?",
    "Bestand",
    "Geringe Lagermenge",
    "Lieferrückstande erlaubt?",
    "Nur einzeln verkaufen?",
    "Gewicht (kg)",
    "Länge (cm)",
    "Breite (cm)",
    "Höhe (cm)",
    "Kundenrezensionen erlauben?",
    "Hinweis zum Kauf",
    "Angebotspreis",
    "Regulärer Preis",
    "Kategorien",
    "Schlagwörter",
    "Versandklasse",
    "Bilder",
    "Downloadlimit",
    "Ablauftage des Downloads",
    "Übergeordnetes Produkt",
    "Gruppierte Produkte",
    "Zusatzverkäufe",
    "Cross-Sells (Querverkäufe)",
    "Externe URL",
    "Button-Text",
    "Position",
    "Marken",
    "Attribut 1 Name",
    "Attribut 1 Wert(e)",
    "Attribut 1 Sichtbar",
    "Attribut 1 Global",
    "Attribut 2 Name",
    "Attribut 2 Wert(e)",
    "Attribut 2 Sichtbar",
    "Attribut 2 Global",
    "Attribut 3 Name",
    "Attribut 3 Wert(e)",
    "Attribut 3 Sichtbar",
    "Attribut 3 Global",
    "Attribut 4 Name",
    "Attribut 4 Wert(e)",
    "Attribut 4 Sichtbar",
    "Attribut 4 Global",
    "Attribut 1 Standard",
    "Attribut 2 Standard",
    "Attribut 3 Standard",
    "Attribut 4 Standard",
]

# Priority order for product attributes (most important first)
# Used when mapping simple product attributes to WooCommerce columns
PRODUCT_ATTRIBUTE_PRIORITY = [
    "Designer",
    "IP Rating",
    "Voltage",
    "Certification",
    "Structure",
    "Armatur",
    "Diffusor",
    "Variants",
]


def format_german_decimal(value: float | None, decimal_places: int = 2) -> str:
    """Format number with German decimal separator (comma).

    Args:
        value: Number to format
        decimal_places: Number of decimal places

    Returns:
        Formatted string with comma separator, or empty string if value is None
    """
    if value is None:
        return ""
    return f"{value:.{decimal_places}f}".replace(".", ",")


def _build_attribute_mapping(
    attributes: list[tuple[str, str]], is_global: bool, max_attrs: int = 4
) -> dict[str, Any]:
    """Build WooCommerce attribute mapping from attribute list.

    Args:
        attributes: List of (name, value) tuples
        is_global: Whether to set Global=1 (for variations) or Global=0 (for products)
        max_attrs: Maximum number of attributes to map (default 4)

    Returns:
        Dictionary with Attribut 1-N Name/Wert(e)/Sichtbar/Global columns
    """
    attr_mapping = {}

    for idx, (attr_name, attr_value) in enumerate(attributes[:max_attrs], start=1):
        attr_mapping[f"Attribut {idx} Name"] = attr_name
        attr_mapping[f"Attribut {idx} Wert(e)"] = attr_value
        attr_mapping[f"Attribut {idx} Sichtbar"] = 1  # Visible on product page
        attr_mapping[f"Attribut {idx} Global"] = 1 if is_global else 0

    return attr_mapping


def _map_product_attributes_to_woocommerce(
    product: ProductData,
) -> dict[str, Any]:
    """Map ProductData.attributes to WooCommerce Attribut 1-4 columns.

    Args:
        product: Product data with attributes to map

    Returns:
        Dictionary with Attribut 1-4 Name/Wert(e)/Sichtbar/Global columns
    """
    if not product.attributes:
        return {}

    # Filter to only attributes that exist in product, maintaining priority order
    available_attrs = [
        (name, product.attributes[name])
        for name in PRODUCT_ATTRIBUTE_PRIORITY
        if name in product.attributes
    ]

    return _build_attribute_mapping(available_attrs, is_global=False)


def _map_variation_attributes_to_woocommerce(
    variation_attributes: dict[str, str],
) -> dict[str, Any]:
    """Map variation attributes to WooCommerce Attribut columns.

    For variable products (parent): values are comma-separated lists of ALL options
    For variation products (child): values are single specific selections

    Args:
        variation_attributes: Dict of attribute name to value(s)

    Returns:
        Dictionary with Attribut 1-4 Name/Wert(e)/Sichtbar/Global columns
    """
    if not variation_attributes:
        return {}

    # Convert dict to list of tuples for consistent interface
    attr_list = list(variation_attributes.items())

    return _build_attribute_mapping(attr_list, is_global=True)


def export_to_woocommerce_csv(
    products: list[ProductData],
    output_path: str = "output/products.csv",
    default_price: float = 0.0,
) -> Path:
    """Export products to WooCommerce-compatible CSV format with German headers.

    Args:
        products: List of product data to export
        output_path: Path to output CSV file
        default_price: Default price for products without pricing (default: 0.0)

    Returns:
        Path to created CSV file

    Raises:
        ValueError: If products list is empty
    """
    if not products:
        raise ValueError("Cannot export empty product list")

    # Build DataFrame with WooCommerce columns
    rows = [_product_to_woocommerce_row(product, default_price) for product in products]
    df = pd.DataFrame(rows)

    # Ensure ALL WooCommerce columns are present (even if empty)
    for col in WOOCOMMERCE_GERMAN_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Use only standard WooCommerce columns (no meta: columns)
    df = df[WOOCOMMERCE_GERMAN_COLUMNS]

    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Export to CSV matching schema format exactly
    df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    logger.info(f"Exported {len(products)} products to {output_file}")
    return output_file


def _product_to_woocommerce_row(
    product: ProductData, default_price: float = 0.0
) -> dict[str, Any]:
    """Convert ProductData to WooCommerce CSV row format with German columns.

    Args:
        product: Product data to convert
        default_price: Default price if product.regular_price is None

    Returns:
        Dictionary representing a CSV row with German WooCommerce columns
    """
    # Format images: pipe-separated URLs (first image becomes featured)
    images = "|".join(product.images) if product.images else ""

    # Format categories: comma-separated
    categories = ", ".join(product.categories) if product.categories else "Lighting"

    # Format prices with German decimal separator
    regular_price = format_german_decimal(
        product.regular_price if product.regular_price is not None else default_price
    )
    sale_price = format_german_decimal(product.sale_price)

    # Format weight and dimensions with German decimal separator
    weight = format_german_decimal(product.weight)

    # Base WooCommerce columns (German names)
    row = {
        "ID": "",  # Empty for new products
        "Typ": product.product_type,  # simple, variable, or variation
        "Artikelnummer": product.sku,
        "GTIN, UPC, EAN oder ISBN": product.ean if product.ean else "",
        "Name": product.name,
        "Veröffentlicht": 1,  # 1 = published
        "Ist hervorgehoben?": 0,  # 0 = not featured
        "Sichtbarkeit im Katalog": "visible",
        "Kurzbeschreibung": _truncate_description(product.description, 120),
        "Beschreibung": product.description,
        "Datum, an dem Angebotspreis beginnt": "",
        "Datum, an dem Angebotspreis endet": "",
        "Steuerstatus": "taxable",
        "Steuerklasse": "",
        "Vorrätig?": 1,
        "Bestand": product.stock if product.stock is not None else "",
        "Geringe Lagermenge": "",
        "Lieferrückstande erlaubt?": 0,
        "Nur einzeln verkaufen?": 0,
        "Gewicht (kg)": weight,
        "Länge (cm)": "",
        "Breite (cm)": "",
        "Höhe (cm)": "",
        "Kundenrezensionen erlauben?": 1,
        "Hinweis zum Kauf": "",
        "Angebotspreis": sale_price,
        "Regulärer Preis": regular_price,
        "Kategorien": categories,
        "Schlagwörter": product.manufacturer,  # Use manufacturer as tag
        "Versandklasse": "",  # Empty - to be configured by client
        "Bilder": images,
        "Downloadlimit": "",
        "Ablauftage des Downloads": "",
        "Übergeordnetes Produkt": product.parent_sku if product.parent_sku else "",
        "Gruppierte Produkte": "",
        "Zusatzverkäufe": "",
        "Cross-Sells (Querverkäufe)": "",
        "Externe URL": "",
        "Button-Text": "",
        "Position": 0,
        "Marken": product.manufacturer,  # Brand field
    }

    # Add dimensions if available (with German decimal formatting)
    if product.dimensions:
        if "length" in product.dimensions:
            row["Länge (cm)"] = format_german_decimal(product.dimensions["length"])
        if "width" in product.dimensions:
            row["Breite (cm)"] = format_german_decimal(product.dimensions["width"])
        if "height" in product.dimensions:
            row["Höhe (cm)"] = format_german_decimal(product.dimensions["height"])

    # Map attributes to WooCommerce Attribut 1-4 columns
    # For variable/variation products: use variation_attributes
    # For simple products: use regular attributes
    if (
        product.product_type in ["variable", "variation"]
        and product.variation_attributes
    ):
        attribute_mapping = _map_variation_attributes_to_woocommerce(
            product.variation_attributes
        )
    else:
        attribute_mapping = _map_product_attributes_to_woocommerce(product)

    row.update(attribute_mapping)

    # Set parent product reference for variations
    if product.product_type == "variation" and product.parent_sku:
        row["Übergeordnetes Produkt"] = f"id:{product.parent_sku}"

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
