"""Vibia price list data extracted from Preisliste_DE_Nov_2024.pdf.

This module contains product codes, prices, and specifications from the
Vibia 2024 Price List for Germany.

Data structure follows the same pattern as lodes_price_list.py for consistency.
"""

import json
from pathlib import Path
from typing import TypedDict

from loguru import logger


class ProductVariant(TypedDict):
    """Price list variant data for Vibia products."""

    sku: str  # Full or simplified SKU (e.g., "0162 10/1A_18" or "0162/1")
    surface_code: str  # Surface finish code (e.g., "10")
    surface_name_en: str  # English surface name
    surface_name_de: str  # German surface name
    led_code: str  # LED color temperature code (e.g., "1")
    led_name_en: str  # English LED description
    led_name_de: str  # German LED description
    control_code: str  # Control system code (e.g., "1")
    control_name_en: str  # English control description
    control_name_de: str  # German control description
    price_eur: float  # Price in EUR (VAT excluded)


class ProductDimensions(TypedDict, total=False):
    """Product dimensions in centimeters."""

    diameter: float  # Diameter in cm (for circular products)
    length: float  # Length in cm
    width: float  # Width in cm
    height: float  # Height in cm


class ProductInfo(TypedDict):
    """Price list product information for Vibia."""

    base_sku: str  # Base model number (e.g., "0162")
    product_name: str  # Full product name (e.g., "Circus Pendelleuchte Ø 20 cm")
    url_slug: str  # URL slug for the product (e.g., "circus")
    category_prefix: str  # Category for URL construction (e.g., "pendelleuchten")
    product_type_suffix: str  # Product type suffix for URL (e.g., "pendelleuchte")
    variants: list[ProductVariant]  # List of configuration variants
    designer: str  # Designer name (e.g., "Antoni Arola")
    voltage: str  # Voltage specification
    ip_rating: str  # IP rating (e.g., "IP20")
    dimensions: ProductDimensions | None  # Product dimensions


# Surface finish codes for Vibia products
SURFACE_CODES = {
    "10": {"en": "Black", "de": "Schwarz", "code": "TIV"},
    "24": {"en": "Beige M1", "de": "Beige M1", "code": "24J"},
}

# LED color temperature codes
LED_CODES = {
    "0": {"en": "No LED", "de": "Ohne LED"},
    "1": {"en": "2700 K", "de": "2700 K"},
    "2": {"en": "3000 K", "de": "3000 K"},
    "3": {"en": "3500 K", "de": "3500 K"},
    "4": {"en": "4000 K", "de": "4000 K"},
    "5": {"en": "Plate", "de": "Plate"},
    "6": {"en": "Tunable White", "de": "Tunable White"},
    "9": {"en": "Tunable Red", "de": "Tunable Red"},
    "A": {"en": "Infinite Colour (TW + RGB)", "de": "Infinite Colour (TW + RGB)"},
    "F": {"en": "Dim-To-Warm", "de": "Dim-To-Warm"},
}

# Control system codes
CONTROL_CODES = {
    "0": {"en": "On/Off", "de": "On/Off"},
    "1": {"en": "DALI-2", "de": "DALI-2"},
    "2": {"en": "0-10V", "de": "0-10V"},
    "3": {"en": "1-10V", "de": "1-10V"},
    "4": {"en": "TRIAC", "de": "TRIAC"},
    "5": {"en": "Phase", "de": "Phase"},
    "6": {"en": "Sensor", "de": "Sensor"},
    "7": {"en": "Lutron", "de": "Lutron"},
    "8": {"en": "Push 2", "de": "Push 2"},
    "A": {"en": "Push; 1-10V; DALI-2", "de": "Push; 1-10V; DALI-2"},
    "Y": {"en": "ProtoPixel", "de": "ProtoPixel"},
    "Z": {"en": "Casambi", "de": "Casambi"},
}

# Circus product family from Preisliste_DE_Nov_2024.pdf
CIRCUS_PRODUCTS: dict[str, ProductInfo] = {
    # Circus Pendelleuchte Ø 20 cm
    "0162": {
        "base_sku": "0162",
        "product_name": "Circus Pendelleuchte Ø 20 cm",
        "url_slug": "circus",
        "category_prefix": "pendelleuchten",
        "product_type_suffix": "pendelleuchte",
        "designer": "Antoni Arola",
        "voltage": "2700 K - 3000 K - 3500K; 1 x LED 6,7 W 600 mA",
        "ip_rating": "IP20",
        "dimensions": {"diameter": 20.0, "height": 20.0},
        "variants": [
            {
                "sku": "0162/1",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "1",
                "led_name_en": "Static White + DALI-2",
                "led_name_de": "Static White + DALI-2",
                "control_code": "1",
                "control_name_en": "DALI-2",
                "control_name_de": "DALI-2",
                "price_eur": 350.00,
            },
            {
                "sku": "0162/Y",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Static White + ProtoPixel (P3P)",
                "led_name_de": "Static White + ProtoPixel (P3P)",
                "control_code": "Y",
                "control_name_en": "ProtoPixel",
                "control_name_de": "ProtoPixel",
                "price_eur": 455.00,
            },
            {
                "sku": "0162/Z",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Static White + Casambi (P3P)",
                "led_name_de": "Static White + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 515.00,
            },
            {
                "sku": "0162/BY",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Tunable White + ProtoPixel (P3P)",
                "led_name_de": "Tunable White + ProtoPixel (P3P)",
                "control_code": "Y",
                "control_name_en": "ProtoPixel",
                "control_name_de": "ProtoPixel",
                "price_eur": 510.00,
            },
            {
                "sku": "0162/BZ",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Tunable Red + Casambi (P3P)",
                "led_name_de": "Tunable Red + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 550.00,
            },
            {
                "sku": "0162/9Z",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "9",
                "led_name_en": "Tunable Red + Casambi (P3P)",
                "led_name_de": "Tunable Red + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 580.00,
            },
        ],
    },
    # Circus Pendelleuchte Ø 45 cm
    "0167": {
        "base_sku": "0167",
        "product_name": "Circus Pendelleuchte Ø 45 cm",
        "url_slug": "circus",
        "category_prefix": "pendelleuchten",
        "product_type_suffix": "pendelleuchte",
        "designer": "Antoni Arola",
        "voltage": "2700 K - 3000 K - 3500K",
        "ip_rating": "IP20",
        "dimensions": {"diameter": 45.0, "height": 45.0},
        "variants": [
            {
                "sku": "0167/1",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "1",
                "led_name_en": "Static White + DALI-2",
                "led_name_de": "Static White + DALI-2",
                "control_code": "1",
                "control_name_en": "DALI-2",
                "control_name_de": "DALI-2",
                "price_eur": 465.00,
            },
            {
                "sku": "0167/Y",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Static White + ProtoPixel (P3P)",
                "led_name_de": "Static White + ProtoPixel (P3P)",
                "control_code": "Y",
                "control_name_en": "ProtoPixel",
                "control_name_de": "ProtoPixel",
                "price_eur": 590.00,
            },
            {
                "sku": "0167/Z",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Static White + Casambi (P3P)",
                "led_name_de": "Static White + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 620.00,
            },
            {
                "sku": "0167/BY",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Tunable White + ProtoPixel (P3P)",
                "led_name_de": "Tunable White + ProtoPixel (P3P)",
                "control_code": "Y",
                "control_name_en": "ProtoPixel",
                "control_name_de": "ProtoPixel",
                "price_eur": 635.00,
            },
            {
                "sku": "0167/BZ",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Tunable White + Casambi (P3P)",
                "led_name_de": "Tunable White + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 665.00,
            },
            {
                "sku": "0167/9Z",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "9",
                "led_name_en": "Tunable Red + Casambi (P3P)",
                "led_name_de": "Tunable Red + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 685.00,
            },
        ],
    },
    # Circus Direkt an der Schiene Ø 20 cm
    "0164": {
        "base_sku": "0164",
        "product_name": "Circus Direkt an der Schiene Ø 20 cm",
        "url_slug": "circus",
        "category_prefix": "pendelleuchten",
        "product_type_suffix": "pendelleuchte",
        "designer": "Antoni Arola",
        "voltage": "Static White",
        "ip_rating": "IP20",
        "dimensions": {"diameter": 20.0},
        "variants": [
            {
                "sku": "0164/1",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "1",
                "led_name_en": "Static White + DALI-2",
                "led_name_de": "Static White + DALI-2",
                "control_code": "1",
                "control_name_en": "DALI-2",
                "control_name_de": "DALI-2",
                "price_eur": 295.00,
            },
            {
                "sku": "0164/Y",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Static White + ProtoPixel (P3P)",
                "led_name_de": "Static White + ProtoPixel (P3P)",
                "control_code": "Y",
                "control_name_en": "ProtoPixel",
                "control_name_de": "ProtoPixel",
                "price_eur": 450.00,
            },
            {
                "sku": "0164/Z",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Static White + Casambi (P3P)",
                "led_name_de": "Static White + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 480.00,
            },
            {
                "sku": "0164/BY",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Tunable White + ProtoPixel (P3P)",
                "led_name_de": "Tunable White + ProtoPixel (P3P)",
                "control_code": "Y",
                "control_name_en": "ProtoPixel",
                "control_name_de": "ProtoPixel",
                "price_eur": 495.00,
            },
            {
                "sku": "0164/BZ",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Tunable White + Casambi (P3P)",
                "led_name_de": "Tunable White + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 525.00,
            },
            {
                "sku": "0164/BY",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "6",
                "led_name_en": "Tunable Red + ProtoPixel (P3P)",
                "led_name_de": "Tunable Red + ProtoPixel (P3P)",
                "control_code": "Y",
                "control_name_en": "ProtoPixel",
                "control_name_de": "ProtoPixel",
                "price_eur": 535.00,
            },
            {
                "sku": "0164/9Z",
                "surface_code": "10",
                "surface_name_en": "Black",
                "surface_name_de": "Schwarz",
                "led_code": "9",
                "led_name_en": "Tunable Red + Casambi (P3P)",
                "led_name_de": "Tunable Red + Casambi (P3P)",
                "control_code": "Z",
                "control_name_en": "Casambi",
                "control_name_de": "Casambi",
                "price_eur": 545.00,
            },
        ],
    },
}

# All products combined
ALL_PRODUCTS: dict[str, ProductInfo] = {
    **CIRCUS_PRODUCTS,
}


def _load_json_price_list() -> dict[str, ProductInfo]:
    """Load price list from JSON file if available.

    Returns:
        Dictionary mapping model numbers to ProductInfo, or empty dict if file not found
    """
    json_path = Path("output/vibia_price_list_data.json")

    if not json_path.exists():
        logger.debug(f"JSON price list not found at {json_path}, using hardcoded data")
        return {}

    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} products from {json_path}")
            return data
    except Exception as e:
        logger.error(f"Failed to load JSON price list: {e}")
        return {}


# Load JSON data if available, otherwise use hardcoded data
_JSON_PRODUCTS = _load_json_price_list()
PRODUCTS = _JSON_PRODUCTS if _JSON_PRODUCTS else ALL_PRODUCTS


def get_product_by_model(model: str) -> ProductInfo | None:
    """Get product information by model number.

    Args:
        model: Model number (e.g., "0162")

    Returns:
        ProductInfo if found, None otherwise
    """
    return PRODUCTS.get(model)


def get_product_by_slug(slug: str) -> list[ProductInfo]:
    """Get all products matching a URL slug.

    Args:
        slug: URL slug (e.g., "circus")

    Returns:
        List of ProductInfo objects with matching slug
    """
    return [p for p in PRODUCTS.values() if p["url_slug"] == slug]


def get_variant_price(sku: str) -> float | None:
    """Get price for a specific variant SKU.

    Args:
        sku: Full or simplified SKU (e.g., "0162/1")

    Returns:
        Price in EUR if found, None otherwise
    """
    # Extract model from SKU (first 4 digits)
    model = sku[:4]
    product = get_product_by_model(model)

    if not product:
        return None

    # Find matching variant
    for variant in product["variants"]:
        if variant["sku"] == sku:
            return variant["price_eur"]

    return None


def get_all_variants(product: ProductInfo) -> list[ProductVariant]:
    """Get all variants for a product.

    Args:
        product: ProductInfo object

    Returns:
        List of product variants
    """
    return product["variants"]


def get_category_for_slug(slug: str) -> str | None:
    """Get category prefix for a product slug.

    Args:
        slug: URL slug (e.g., "circus")

    Returns:
        Category prefix (e.g., "pendelleuchten") if found, None otherwise
    """
    products = get_product_by_slug(slug)
    if products:
        return products[0]["category_prefix"]
    return None


def parse_sku_components(full_sku: str) -> dict[str, str] | None:
    """Parse a full SKU into its components.

    Args:
        full_sku: Full SKU string (e.g., "1160 10 / 1A _ 18")

    Returns:
        Dictionary with components: model, surface, led, control, connection
        None if SKU format is invalid
    """
    import re

    # Try full format: "1160 10 / 1A _ 18"
    full_match = re.match(
        r"(\d{4})\s+(\d{2})\s*/\s*([0-9A-F])([0-9A-Z])\s*_\s*(\d{2})", full_sku
    )
    if full_match:
        return {
            "model": full_match.group(1),
            "surface": full_match.group(2),
            "led": full_match.group(3),
            "control": full_match.group(4),
            "connection": full_match.group(5),
        }

    # Try simplified format: "0162/1"
    simple_match = re.match(r"(\d{4})/(.+)", full_sku)
    if simple_match:
        return {
            "model": simple_match.group(1),
            "variant_code": simple_match.group(2),
        }

    return None


def build_full_sku(
    model: str, surface: str, led: str, control: str, connection: str
) -> str:
    """Build a full SKU from components.

    Args:
        model: Model number (4 digits)
        surface: Surface finish code (2 digits)
        led: LED color temperature code (1 char)
        control: Control system code (1 char)
        connection: Electrical connection code (2 digits)

    Returns:
        Full SKU string (e.g., "1160 10 / 1A _ 18")
    """
    return f"{model} {surface} / {led}{control} _ {connection}"
