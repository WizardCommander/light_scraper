"""Lodes price list PDF parser."""

import json
import os
import re
from typing import Any

from loguru import logger

from scripts.parsers.pdf_parser_base import (
    PDFParserBase,
    ParsingStats,
    validate_price,
    validate_sku,
)
from scripts.parsers.lodes_color_codes import parse_lodes_color_code
from scripts.parsers.sku_mapping_loader import load_sku_mapping

# Load auto-generated SKU mapping
SKU_MAPPING = load_sku_mapping(
    mapping_filename="lodes_sku_mapping_auto.json",
    sku_pattern=r"^\d{4,5}$",
    manufacturer="Lodes",
)


# Original color code mapping from src/lodes_price_list.py (for backward compatibility)
COLOR_CODES = {
    "1000": {
        "en": "Matte White",
        "de": "Weiß Matt",
        "it": "Bianco Opaco",
        "code_suffix": "9010",
    },
    "2000": {
        "en": "Matte Black",
        "de": "Schwarz Matt",
        "it": "Nero Opaco",
        "code_suffix": "9005",
    },
    "3500": {"en": "Coppery Bronze", "de": "Bronze", "it": "Bronzo Ramato"},
    "4500": {
        "en": "Matte Champagne",
        "de": "Champagner Matt",
        "it": "Champagne Opaco",
    },
}


class LodesTableParser(PDFParserBase):
    """Parser for Lodes PDF price lists."""

    # SKU pattern: 5 digits, space, 4 digits (e.g., "14126 1000")
    SKU_PATTERN = r"(\d{5})\s+(\d{4})"

    def __init__(self, pdf_path: str, start_page: int = 5, end_page: int = 6):
        """Initialize Lodes parser.

        Args:
            pdf_path: Path to Lodes PDF file
            start_page: Start page (1-indexed as shown in PDF viewer, default: 5)
            end_page: End page (1-indexed as shown in PDF viewer, default: 6)
        """
        super().__init__(pdf_path)
        # Convert to 0-indexed
        self.start_page = start_page - 1
        self.end_page = end_page - 1

    def parse_price_list(self) -> dict[str, Any]:
        """Parse Lodes price list and extract all products.

        Returns:
            Dictionary with metadata and products
        """
        self.load_pdf()
        stats = ParsingStats()

        # Process each page individually (SKUs and prices on same page belong together)
        all_products: dict[str, Any] = {}
        for page_idx in range(self.start_page, self.end_page + 1):
            logger.info(f"Processing page {page_idx + 1}")
            page_text = self.extract_page_text(page_idx)
            page_products = self._parse_page(page_text, stats)
            all_products.update(page_products)

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
        """Parse a single page extracting SKUs and prices.

        Args:
            text: Page text
            stats: Statistics tracker

        Returns:
            Dictionary mapping base SKUs to ProductInfo dicts
        """
        lines = text.split("\n")

        # Extract SKUs and prices
        skus = self._extract_skus_from_lines(lines)
        prices = self._extract_prices_from_text(text)

        logger.debug(f"Found {len(skus)} SKUs and {len(prices)} prices on page")

        # Warn if counts don't match
        if len(skus) != len(prices):
            logger.warning(
                f"SKU count ({len(skus)}) != price count ({len(prices)}) on page"
            )

        # Create variants from SKUs and prices
        variants_by_base, product_names = self._create_variants_from_skus_and_prices(
            skus, prices, stats
        )

        # Build final product entries
        products = self._build_products_from_variants(
            variants_by_base, product_names, stats
        )

        return products

    def _extract_skus_from_lines(
        self, lines: list[str]
    ) -> list[tuple[str, str, str, str | None]]:
        """Extract SKUs and associated product names from text lines.

        Args:
            lines: List of text lines from page

        Returns:
            List of tuples: (base_sku, color_code, full_sku, product_name)
        """
        skus = []
        current_product_name = None

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Check if this line contains a SKU
            sku_match = re.search(self.SKU_PATTERN, line_stripped)
            if sku_match:
                base_sku = sku_match.group(1)
                color_code = sku_match.group(2)
                full_sku = f"{base_sku} {color_code}"
                skus.append((base_sku, color_code, full_sku, current_product_name))
            else:
                # Check if this might be a product name header
                product_name = self._try_extract_product_name(line_stripped, lines, i)
                if product_name:
                    current_product_name = product_name
                    logger.debug(f"Found product name: {current_product_name}")

        return skus

    def _try_extract_product_name(
        self, line: str, lines: list[str], line_idx: int
    ) -> str | None:
        """Try to extract a product name from a line.

        Product names are typically short (1-4 words), alphabetic, and appear before SKUs.

        Args:
            line: Line to check
            lines: All lines from page
            line_idx: Index of current line

        Returns:
            Product name if found, None otherwise
        """
        if not line or len(line) >= 50:
            return None

        # Simple heuristic: line with mostly letters and spaces, no numbers
        if not re.match(r"^[A-Za-z][A-Za-z\s\-]+[a-z]?$", line):
            return None

        # Check if next few lines contain SKUs (validates this is a product header)
        next_lines = lines[line_idx + 1 : line_idx + 5]
        if any(re.search(self.SKU_PATTERN, next_line) for next_line in next_lines):
            return line

        return None

    def _extract_prices_from_text(self, text: str) -> list[float]:
        """Extract all prices from text in order.

        Prices are in format: "572,00" or "1234,50"

        Args:
            text: Page text

        Returns:
            List of prices in EUR
        """
        prices = []
        price_pattern = r"^(\d{3,5}),(\d{2})$"

        for line in text.split("\n"):
            line = line.strip()
            price_match = re.match(price_pattern, line)
            if price_match:
                price_str = f"{price_match.group(1)}.{price_match.group(2)}"
                try:
                    price = float(price_str)
                    if validate_price(price):
                        prices.append(price)
                except ValueError:
                    continue

        return prices

    def _create_variants_from_skus_and_prices(
        self,
        skus: list[tuple[str, str, str, str | None]],
        prices: list[float],
        stats: ParsingStats,
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
        """Create product variants by matching SKUs with prices.

        Args:
            skus: List of (base_sku, color_code, full_sku, product_name) tuples
            prices: List of prices in order
            stats: Statistics tracker

        Returns:
            Tuple of (variants_by_base_sku, product_names_by_base_sku)
        """
        variants_by_base: dict[str, list[dict[str, Any]]] = {}
        product_names: dict[str, str] = {}

        for i, (base_sku, color_code, full_sku, product_name) in enumerate(skus):
            # Get corresponding price
            if i >= len(prices):
                stats.add_warning(f"No price for SKU {full_sku}")
                continue

            price = prices[i]

            # Resolve color names
            color_name_en, color_name_de = self._resolve_color_names(
                color_code, full_sku, stats
            )

            # Create variant
            variant = {
                "sku": full_sku,
                "color_code": color_code,
                "color_name_en": color_name_en,
                "color_name_de": color_name_de,
                "price_eur": price,
            }

            # Group by base SKU
            if base_sku not in variants_by_base:
                variants_by_base[base_sku] = []
            variants_by_base[base_sku].append(variant)

            # Store product name for this base SKU
            if product_name and base_sku not in product_names:
                product_names[base_sku] = product_name

            logger.debug(f"Parsed variant: {full_sku} - {color_name_en} - €{price}")

        return variants_by_base, product_names

    def _resolve_color_names(
        self, color_code: str, full_sku: str, stats: ParsingStats
    ) -> tuple[str, str]:
        """Resolve color code to English and German names.

        Args:
            color_code: Color code (e.g., "1000", "1027")
            full_sku: Full SKU for warning messages
            stats: Statistics tracker

        Returns:
            Tuple of (color_name_en, color_name_de)
        """
        color_info = COLOR_CODES.get(color_code)
        if color_info:
            # Use original mapping for 4-digit codes (1000, 2000, etc.)
            return color_info["en"], color_info["de"]

        # Try extended color code parsing for other formats
        parsed = parse_lodes_color_code(color_code)
        color_name_en = parsed["color_name_en"]
        color_name_de = parsed["color_name_de"]

        # Only warn if it's truly unknown (not in extended mapping either)
        if "Color" in color_name_en:
            stats.add_warning(f"Unknown color code {color_code} for SKU {full_sku}")

        return color_name_en, color_name_de

    def _build_products_from_variants(
        self,
        variants_by_base: dict[str, list[dict[str, Any]]],
        product_names: dict[str, str],
        stats: ParsingStats,
    ) -> dict[str, Any]:
        """Build final product entries from variants.

        Args:
            variants_by_base: Variants grouped by base SKU
            product_names: Product names extracted from PDF
            stats: Statistics tracker

        Returns:
            Dictionary mapping base SKUs to ProductInfo dicts
        """
        products = {}

        for base_sku, variants in variants_by_base.items():
            variants = self._deduplicate_variants(variants)

            # Get product name and URL slug
            # Priority: 1) Auto-generated mapping, 2) Extracted from PDF, 3) Default
            if base_sku in SKU_MAPPING:
                mapping_info = SKU_MAPPING[base_sku]
                product_name = mapping_info["product_name"]
                url_slug = mapping_info["url_slug"]
            else:
                product_name = product_names.get(base_sku, f"Product {base_sku}")
                url_slug = self._product_name_to_slug(product_name)

            products[base_sku] = {
                "base_sku": base_sku,
                "product_name": product_name,
                "url_slug": url_slug,
                "variants": variants,
                "cable_length": "",
                "light_source": "",
                "dimmability": "",
                "voltage": "",
                "ip_rating": "",
                "dimensions": None,
            }

            stats.add_product(base_sku, len(variants))

        return products

    def _deduplicate_variants(
        self, variants: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Deduplicate variants by color code, keeping highest price.

        Args:
            variants: List of variant dicts

        Returns:
            Deduplicated list of variants
        """
        by_color: dict[str, dict[str, Any]] = {}

        for variant in variants:
            color_code = variant["color_code"]
            if color_code not in by_color:
                by_color[color_code] = variant
            else:
                # Keep variant with higher price
                if variant["price_eur"] > by_color[color_code]["price_eur"]:
                    by_color[color_code] = variant

        return list(by_color.values())

    def _product_name_to_slug(self, product_name: str) -> str:
        """Convert product name to URL slug.

        Args:
            product_name: Product name (e.g., "Aile a", "Kelly Dome")

        Returns:
            URL slug (e.g., "aile", "kelly-dome")
        """
        # If it starts with "Product ", return "unknown"
        if product_name.startswith("Product "):
            return "unknown"

        # Convert to lowercase, remove extra spaces, replace spaces with hyphens
        slug = product_name.lower().strip()
        # Remove variant indicators (letters at the end like " a", " b")
        slug = re.sub(r"\s+[a-z]$", "", slug)
        # Replace spaces with hyphens
        slug = re.sub(r"\s+", "-", slug)
        # Remove any non-alphanumeric characters except hyphens
        slug = re.sub(r"[^a-z0-9\-]", "", slug)
        # Remove consecutive hyphens
        slug = re.sub(r"-+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")

        return slug if slug else "unknown"
