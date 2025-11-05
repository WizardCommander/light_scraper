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


@dataclass
class ScraperConfig:
    """Configuration for a manufacturer scraper."""

    manufacturer: Manufacturer
    base_url: str
    rate_limit_delay: float = 1.0  # seconds between requests
    max_retries: int = 3
    timeout: int = 30  # seconds
