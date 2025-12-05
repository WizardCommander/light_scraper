"""Lodes 2025 Price List data extracted from PDF.

This module contains product codes, prices, and specifications from the
Lodes 2025 Price List for Europa.
"""

from typing import TypedDict


class ProductVariant(TypedDict):
    """Price list variant data."""

    sku: str  # Full SKU with color code (e.g., "14126 1000")
    color_code: str  # Color code only (e.g., "1000")
    color_name_en: str  # English color name (e.g., "Matte White")
    color_name_de: str  # German color name (e.g., "Weiß Matt")
    price_eur: float  # Price in EUR (VAT excluded)


class ProductDimensions(TypedDict, total=False):
    """Product dimensions in centimeters."""

    length: float  # Length in cm
    width: float  # Width in cm
    height: float  # Height in cm


class ProductInfo(TypedDict):
    """Price list product information."""

    base_sku: str  # Base SKU without color code (e.g., "14126")
    product_name: str  # Full product name (e.g., "Kelly small dome 50")
    url_slug: str  # URL slug for the product (e.g., "kelly")
    variants: list[ProductVariant]  # List of color variants
    cable_length: str  # Cable/rope length (e.g., "max 250cm")
    light_source: str  # Light source specification
    dimmability: str  # Dimmability type (e.g., "TRIAC")
    voltage: str  # Voltage specification
    ip_rating: str  # IP rating (e.g., "IP20")
    dimensions: ProductDimensions | None  # Product dimensions (length, width, height in cm)


# Color code mapping
COLOR_CODES = {
    "1000": {"en": "Matte White", "de": "Weiß Matt", "it": "Bianco Opaco", "code_suffix": "9010"},
    "2000": {"en": "Matte Black", "de": "Schwarz Matt", "it": "Nero Opaco", "code_suffix": "9005"},
    "3500": {"en": "Coppery Bronze", "de": "Bronze", "it": "Bronzo Ramato"},
    "4500": {"en": "Matte Champagne", "de": "Champagner Matt", "it": "Champagne Opaco"},
}

# Kelly product family price list data
# Extracted from Lodes-2025 Price List-Europa neue Version.pdf pages 8-9
KELLY_PRODUCTS: dict[str, ProductInfo] = {
    # Kelly Dome series
    "14126": {
        "base_sku": "14126",
        "product_name": "Kelly small dome 50",
        "url_slug": "kelly",
        "cable_length": "max 250cm",
        "light_source": "E27 LED B / L max 12cm\n3× 25 W",
        "dimmability": "TRIAC",
        "voltage": "220-240V",
        "ip_rating": "IP20",
        "dimensions": {"length": 50.0, "width": 50.0, "height": 30.0},
        "variants": [
            {
                "sku": "14126 1000",
                "color_code": "1000",
                "color_name_en": "Matte White",
                "color_name_de": "Weiß Matt",
                "price_eur": 572.00,
            },
            {
                "sku": "14126 2000",
                "color_code": "2000",
                "color_name_en": "Matte Black",
                "color_name_de": "Schwarz Matt",
                "price_eur": 572.00,
            },
            {
                "sku": "14126 3500",
                "color_code": "3500",
                "color_name_en": "Coppery Bronze",
                "color_name_de": "Bronze",
                "price_eur": 607.00,
            },
            {
                "sku": "14126 4500",
                "color_code": "4500",
                "color_name_en": "Matte Champagne",
                "color_name_de": "Champagner Matt",
                "price_eur": 607.00,
            },
        ],
    },
    "14127": {
        "base_sku": "14127",
        "product_name": "Kelly medium dome 60",
        "url_slug": "kelly",
        "cable_length": "max 250cm",
        "light_source": "E27 LED B / L max 12cm\n3× 25 W",
        "dimmability": "TRIAC",
        "voltage": "220-240V",
        "ip_rating": "IP20",
        "variants": [
            {
                "sku": "14127 1000",
                "color_code": "1000",
                "color_name_en": "Matte White",
                "color_name_de": "Weiß Matt",
                "price_eur": 883.00,
            },
            {
                "sku": "14127 2000",
                "color_code": "2000",
                "color_name_en": "Matte Black",
                "color_name_de": "Schwarz Matt",
                "price_eur": 883.00,
            },
            {
                "sku": "14127 3500",
                "color_code": "3500",
                "color_name_en": "Coppery Bronze",
                "color_name_de": "Bronze",
                "price_eur": 913.00,
            },
            {
                "sku": "14127 4500",
                "color_code": "4500",
                "color_name_en": "Matte Champagne",
                "color_name_de": "Champagner Matt",
                "price_eur": 913.00,
            },
        ],
    },
    "14128": {
        "base_sku": "14128",
        "product_name": "Kelly large dome 80",
        "url_slug": "kelly",
        "cable_length": "max 250cm",
        "light_source": "E27 LED B / L max 12cm\n3× 25 W",
        "dimmability": "TRIAC",
        "voltage": "220-240V",
        "ip_rating": "IP20",
        "variants": [
            {
                "sku": "14128 1000",
                "color_code": "1000",
                "color_name_en": "Matte White",
                "color_name_de": "Weiß Matt",
                "price_eur": 1102.00,
            },
            {
                "sku": "14128 2000",
                "color_code": "2000",
                "color_name_en": "Matte Black",
                "color_name_de": "Schwarz Matt",
                "price_eur": 1102.00,
            },
            {
                "sku": "14128 3500",
                "color_code": "3500",
                "color_name_en": "Coppery Bronze",
                "color_name_de": "Bronze",
                "price_eur": 1153.00,
            },
            {
                "sku": "14128 4500",
                "color_code": "4500",
                "color_name_en": "Matte Champagne",
                "color_name_de": "Champagner Matt",
                "price_eur": 1153.00,
            },
        ],
    },
    # Kelly Sphere series
    "14122": {
        "base_sku": "14122",
        "product_name": "Kelly small sphere 40",
        "url_slug": "kelly",
        "cable_length": "max 250cm",
        "light_source": "E27 LED B / L max 12cm\n3× 25 W",
        "dimmability": "TRIAC",
        "voltage": "220-240V",
        "ip_rating": "IP20",
        "variants": [
            {
                "sku": "14122 1000",
                "color_code": "1000",
                "color_name_en": "Matte White",
                "color_name_de": "Weiß Matt",
                "price_eur": 913.00,
            },
            {
                "sku": "14122 3500",
                "color_code": "3500",
                "color_name_en": "Coppery Bronze",
                "color_name_de": "Bronze",
                "price_eur": 939.00,
            },
        ],
    },
    "14123": {
        "base_sku": "14123",
        "product_name": "Kelly medium sphere 50",
        "url_slug": "kelly",
        "cable_length": "max 250cm",
        "light_source": "E27 LED B / L max 12cm\n3× 25 W",
        "dimmability": "TRIAC",
        "voltage": "220-240V",
        "ip_rating": "IP20",
        "variants": [
            {
                "sku": "14123 1000",
                "color_code": "1000",
                "color_name_en": "Matte White",
                "color_name_de": "Weiß Matt",
                "price_eur": 1214.00,
            },
            {
                "sku": "14123 3500",
                "color_code": "3500",
                "color_name_en": "Coppery Bronze",
                "color_name_de": "Bronze",
                "price_eur": 1240.00,
            },
        ],
    },
    "14124": {
        "base_sku": "14124",
        "product_name": "Kelly large sphere 80",
        "url_slug": "kelly",
        "cable_length": "max 250cm",
        "light_source": "E27 LED B / L max 12cm\n3× 25 W",
        "dimmability": "TRIAC",
        "voltage": "220-240V",
        "ip_rating": "IP20",
        "variants": [
            {
                "sku": "14124 1000",
                "color_code": "1000",
                "color_name_en": "Matte White",
                "color_name_de": "Weiß Matt",
                "price_eur": 3264.00,
            },
            {
                "sku": "14124 3500",
                "color_code": "3500",
                "color_name_en": "Coppery Bronze",
                "color_name_de": "Bronze",
                "price_eur": 3326.00,
            },
        ],
    },
    # Kelly Cluster
    "14711": {
        "base_sku": "14711",
        "product_name": "Kelly Cluster",
        "url_slug": "kelly",
        "cable_length": "max 400cm",
        "light_source": "LED\n2700 K\n7 W\n1280 lm\n350 mA\nCRI 90\nMacAdam 3-Step\nLED and driver included",
        "dimmability": "TRIAC",
        "voltage": "220-240V",
        "ip_rating": "IP20",
        "variants": [
            {
                "sku": "14711 1027",
                "color_code": "1027",
                "color_name_en": "Matte White",
                "color_name_de": "Weiß Matt",
                "price_eur": 388.00,
            },
            {
                "sku": "14711 2027",
                "color_code": "2027",
                "color_name_en": "Matte Black",
                "color_name_de": "Schwarz Matt",
                "price_eur": 388.00,
            },
            {
                "sku": "14711 3527",
                "color_code": "3527",
                "color_name_en": "Coppery Bronze",
                "color_name_de": "Bronze",
                "price_eur": 403.00,
            },
            {
                "sku": "14711 4527",
                "color_code": "4527",
                "color_name_en": "Matte Champagne",
                "color_name_de": "Champagner Matt",
                "price_eur": 403.00,
            },
        ],
    },
}


def get_product_by_slug(slug: str) -> list[ProductInfo]:
    """Get all products matching a URL slug.

    Args:
        slug: URL slug (e.g., "kelly")

    Returns:
        List of matching ProductInfo dictionaries
    """
    return [p for p in KELLY_PRODUCTS.values() if p["url_slug"] == slug]


def get_product_by_base_sku(base_sku: str) -> ProductInfo | None:
    """Get product by base SKU.

    Args:
        base_sku: Base SKU (e.g., "14126")

    Returns:
        ProductInfo dictionary or None if not found
    """
    return KELLY_PRODUCTS.get(base_sku)


def get_variant_price(sku: str) -> float | None:
    """Get price for a variant SKU.

    Args:
        sku: Full variant SKU (e.g., "14126 1000")

    Returns:
        Price in EUR or None if not found
    """
    # Extract base SKU (first part before space)
    base_sku = sku.split()[0] if " " in sku else sku

    product = KELLY_PRODUCTS.get(base_sku)
    if not product:
        return None

    # Find matching variant
    for variant in product["variants"]:
        if variant["sku"] == sku:
            return variant["price_eur"]

    return None


def get_all_product_colors(product_info: ProductInfo) -> str:
    """Get comma-separated list of all color names in German.

    Args:
        product_info: Product information dictionary

    Returns:
        Comma-separated color names (e.g., "Weiß Matt, Schwarz Matt, Bronze, Champagner Matt")
    """
    colors = [v["color_name_de"] for v in product_info["variants"]]
    return ", ".join(colors)
