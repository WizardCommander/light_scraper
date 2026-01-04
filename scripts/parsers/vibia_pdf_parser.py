"""Vibia price list PDF parser."""

import json
import os
import re
from typing import Any

from loguru import logger

from scripts.parsers.pdf_parser_base import (
    PDFParserBase,
    ParsingStats,
    validate_price,
)
from scripts.parsers.sku_mapping_loader import load_sku_mapping

# Load auto-generated SKU mapping
SKU_MAPPING = load_sku_mapping(
    mapping_filename="vibia_sku_mapping_auto.json",
    sku_pattern=r"^\d{4}$",
    manufacturer="Vibia",
)


# Code mappings from src/vibia_price_list.py
SURFACE_CODES = {
    "10": {"en": "Black", "de": "Schwarz"},
    "24": {"en": "Beige M1", "de": "Beige M1"},
}

LED_CODES = {
    "0": {"en": "No LED", "de": "Ohne LED"},
    "1": {"en": "2700 K", "de": "2700 K"},
    "2": {"en": "3000 K", "de": "3000 K"},
    "6": {"en": "Tunable White", "de": "Tunable White"},
    "9": {"en": "Tunable Red", "de": "Tunable Red"},
}

CONTROL_CODES = {
    "0": {"en": "On/Off", "de": "On/Off"},
    "1": {"en": "DALI-2", "de": "DALI-2"},
    "Z": {"en": "Casambi", "de": "Casambi"},
    "Y": {"en": "ProtoPixel", "de": "ProtoPixel"},
}


class VibiaTableParser(PDFParserBase):
    """Parser for Vibia PDF price lists."""

    # SKU patterns:
    # Simple: "0162/1", "0162/Z", "0162/BY"
    # Full: "0162 10/1A_18"
    SIMPLE_SKU_PATTERN = r"(\d{4})/([A-Z0-9]+)"
    FULL_SKU_PATTERN = r"(\d{4})\s+(\d{2})/([A-Z0-9]+)"

    def __init__(
        self, pdf_path: str, start_page: int | None = None, end_page: int | None = None
    ):
        """Initialize Vibia parser.

        Args:
            pdf_path: Path to Vibia PDF file
            start_page: Start page (1-indexed), None for all pages
            end_page: End page (1-indexed), None for all pages
        """
        super().__init__(pdf_path)
        self.start_page = (start_page - 1) if start_page else None
        self.end_page = (end_page - 1) if end_page else None

    def parse_price_list(self) -> dict[str, Any]:
        """Parse Vibia price list and extract all products.

        Returns:
            Dictionary with metadata and products
        """
        self.load_pdf()
        stats = ParsingStats()

        # Determine page range
        if self.start_page is None:
            self.start_page = 0
        if self.end_page is None:
            if self.reader is None:
                raise RuntimeError("PDF not loaded")
            self.end_page = len(self.reader.pages) - 1

        logger.info(
            f"Processing pages {self.start_page + 1}-{self.end_page + 1} "
            f"({self.end_page - self.start_page + 1} pages)"
        )

        # Process pages in batches to handle large PDF
        all_products: dict[str, Any] = {}
        for page_idx in range(self.start_page, self.end_page + 1):
            if (page_idx - self.start_page) % 50 == 0:
                logger.info(f"Progress: page {page_idx + 1}/{self.end_page + 1}")

            try:
                page_text = self.extract_page_text(page_idx)
                page_products = self._parse_page(page_text, stats)
                all_products.update(page_products)
            except Exception as e:
                stats.add_error(f"Failed to parse page {page_idx + 1}: {e}")
                continue

        stats.print_summary()

        return {
            "metadata": {
                "source_pdf": self.pdf_path,
                "parser_version": "1.0.0",
                "total_products": len(all_products),
                "total_variants": sum(
                    len(p["variants"]) for p in all_products.values()
                ),
            },
            "products": all_products,
        }

    def _parse_page(self, text: str, stats: ParsingStats) -> dict[str, Any]:
        """Parse a single page extracting variant codes and inline prices.

        Args:
            text: Page text
            stats: Statistics tracker

        Returns:
            Dictionary mapping base SKUs to ProductInfo dicts
        """
        # Pattern to find lines with variant code and price
        # Format: "_ _ / _ 1 Static White + DALI-2 360,00 €"
        # or: "_ _ / _ Y Static White + ProtoPixel* (P2P) 485,00 €"
        variant_price_pattern = r"/\s+_?\s*([A-Z0-9]{1,2})\s+.*?(\d{3,5}),(\d{2})\s*€"

        # Find base SKU (e.g., "0162 _ _ / _ _")
        base_sku_pattern = r"(\d{4})\s+_\s+_\s+/\s+_\s+_"

        variants_by_base: dict[str, list[dict[str, Any]]] = {}
        current_base_sku = None

        for line in text.split("\n"):
            # Check for base SKU header
            base_match = re.search(base_sku_pattern, line)
            if base_match:
                current_base_sku = base_match.group(1)
                logger.debug(f"Found base SKU: {current_base_sku}")
                continue

            # Check for variant with price
            if current_base_sku:
                variant_match = re.search(variant_price_pattern, line)
                if variant_match:
                    control_code = variant_match.group(1).strip()
                    price_str = f"{variant_match.group(2)}.{variant_match.group(3)}"

                    try:
                        price = float(price_str)
                        if not validate_price(price):
                            continue
                    except ValueError:
                        continue

                    # Build full SKU
                    full_sku = f"{current_base_sku}/{control_code}"

                    # Parse codes (simplified - using defaults)
                    surface_code = "10"  # Default Black
                    led_code = (
                        control_code[0]
                        if len(control_code) > 1 and control_code[0].isdigit()
                        else "1"
                    )

                    # Get names
                    surface_info = SURFACE_CODES.get(
                        surface_code,
                        {
                            "en": f"Surface {surface_code}",
                            "de": f"Oberfläche {surface_code}",
                        },
                    )
                    led_info = LED_CODES.get(
                        led_code, {"en": f"LED {led_code}", "de": f"LED {led_code}"}
                    )
                    control_info = CONTROL_CODES.get(
                        control_code,
                        {
                            "en": f"Control {control_code}",
                            "de": f"Steuerung {control_code}",
                        },
                    )

                    variant = {
                        "sku": full_sku,
                        "surface_code": surface_code,
                        "surface_name_en": surface_info["en"],
                        "surface_name_de": surface_info["de"],
                        "led_code": led_code,
                        "led_name_en": led_info["en"],
                        "led_name_de": led_info["de"],
                        "control_code": control_code,
                        "control_name_en": control_info["en"],
                        "control_name_de": control_info["de"],
                        "price_eur": price,
                    }

                    if current_base_sku not in variants_by_base:
                        variants_by_base[current_base_sku] = []
                    variants_by_base[current_base_sku].append(variant)

                    logger.debug(f"Parsed variant: {full_sku} - €{price}")

        # Build product entries
        products = {}
        for base_sku, variants in variants_by_base.items():
            # Get product name and URL slug from mapping
            if base_sku in SKU_MAPPING:
                mapping_info = SKU_MAPPING[base_sku]
                product_name = mapping_info["product_name"]
                url_slug = mapping_info["url_slug"]
            else:
                product_name = f"Product {base_sku}"
                url_slug = "unknown"

            products[base_sku] = {
                "base_sku": base_sku,
                "product_name": product_name,
                "url_slug": url_slug,
                "category_prefix": "pendelleuchten",
                "product_type_suffix": "pendelleuchte",
                "variants": variants,
                "designer": "",
                "voltage": "",
                "ip_rating": "",
                "dimensions": None,
            }

            stats.add_product(base_sku, len(variants))

        return products
