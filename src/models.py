"""Type definitions for the product scraper.

Following CLAUDE.md best practices: use branded types (NewType) for IDs
to prevent mixing different string types.
"""

from dataclasses import dataclass
from typing import Literal, NewType

# Branded types for type safety
SKU = NewType("SKU", str)
ImageUrl = NewType("ImageUrl", str)
ProductUrl = NewType("ProductUrl", str)
EAN = NewType("EAN", str)
Manufacturer = NewType("Manufacturer", str)


ProductType = Literal["simple", "variable", "variation"]


@dataclass
class ProductData:
    """Structured product data extracted from manufacturer websites."""

    sku: SKU
    name: str
    description: str
    manufacturer: Manufacturer
    categories: list[str]
    attributes: dict[str, str]
    images: list[ImageUrl]
    product_type: ProductType = "simple"  # simple, variable, or variation
    parent_sku: SKU | None = None  # For variation products
    variation_attributes: dict[str, str] | None = (
        None  # e.g., {"Size": "Large", "Color": "Red"}
    )
    regular_price: float | None = None
    sale_price: float | None = None
    stock: int | None = None
    ean: EAN | None = None
    weight: float | None = None
    dimensions: dict[str, float] | None = None  # length, width, height
    installation_type: str | None = None  # Montageart (e.g., Wandleuchte, Hängeleuchte)
    material: str | None = None  # Material (e.g., Aluminium, Marmor, Glas)
    ip_rating: str | None = None  # IP Rating (e.g., IP20, IP44, IP65)
    light_specs: dict[str, str] | None = None  # LED specs (wattage, lumen, kelvin)
    datasheet_url: str | None = None  # URL to product datasheet/PDF
    cable_length: str | None = None  # Cable/rope length (e.g., "max 250cm")
    available_colors: str | None = (
        None  # All available colors (e.g., "Weiß, Schwarz, Bronze, Champagner")
    )
    installation_manual_url: str | None = None  # URL to installation manual PDF
    product_notes: str | None = (
        None  # Product information notes (e.g., "Leuchtmittel nicht inkludiert.")
    )
    scraped_language: str = "en"  # Language of scraped content
    translated_to_german: bool = False  # Whether content was AI-translated
    short_description: str | None = None  # AI-generated short description (≤20 words)
    original_name: str | None = None  # Original product name from price list (untranslated)


@dataclass
class ScraperConfig:
    """Configuration for a manufacturer scraper."""

    manufacturer: Manufacturer
    base_url: str
    rate_limit_delay: float = 1.0  # seconds between requests
    max_retries: int = 3
    timeout: int = 30  # seconds
    language_priority: list[str] | None = None  # e.g., ["de", "en"]
    default_price: float = 0.0  # Default price for products without pricing
