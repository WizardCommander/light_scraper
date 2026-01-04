"""Base utilities for parsing manufacturer PDF price lists."""

import json
import os
import re
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from pypdf import PdfReader


class PDFParserBase(ABC):
    """Abstract base class for PDF price list parsers."""

    def __init__(self, pdf_path: str):
        """Initialize parser with PDF path.

        Args:
            pdf_path: Path to the PDF file to parse
        """
        self.pdf_path = pdf_path
        self.reader: PdfReader | None = None

    def load_pdf(self) -> PdfReader:
        """Load PDF file and return reader instance.

        Returns:
            PdfReader instance

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            Exception: If PDF cannot be loaded
        """
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

        try:
            self.reader = PdfReader(self.pdf_path)
            logger.info(f"Loaded PDF: {self.pdf_path} ({len(self.reader.pages)} pages)")
            return self.reader
        except Exception as e:
            logger.error(f"Failed to load PDF {self.pdf_path}: {e}")
            raise

    def extract_page_text(self, page_index: int) -> str:
        """Extract text from a single page.

        Args:
            page_index: 0-based page index

        Returns:
            Extracted text from the page
        """
        if self.reader is None:
            raise RuntimeError("PDF not loaded. Call load_pdf() first.")

        if page_index < 0 or page_index >= len(self.reader.pages):
            raise IndexError(f"Page index {page_index} out of range")

        return self.reader.pages[page_index].extract_text()

    @abstractmethod
    def parse_price_list(self) -> dict[str, Any]:
        """Parse the PDF and extract product data.

        Must be implemented by subclasses.

        Returns:
            Dictionary mapping base SKUs to product data
        """
        pass


def extract_price_eur(text: str) -> float | None:
    """Extract EUR price from text.

    Handles various formats:
    - "572,00 €"
    - "572.00 €"
    - "€ 572,00"
    - "572,00"

    Args:
        text: Text containing price

    Returns:
        Price as float, or None if not found
    """
    # Match price patterns with optional € symbol
    patterns = [
        r"€?\s*([\d,.]+)\s*€?",  # General pattern
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            price_str = match.group(1)
            # Remove spaces and convert comma to period
            price_str = price_str.replace(" ", "").replace(",", ".")
            try:
                price = float(price_str)
                if validate_price(price):
                    return price
            except ValueError:
                continue

    return None


def validate_sku(sku: str, pattern: str) -> bool:
    """Validate SKU format against regex pattern.

    Args:
        sku: SKU string to validate
        pattern: Regex pattern to match

    Returns:
        True if SKU matches pattern
    """
    if not sku or not isinstance(sku, str):
        return False
    return bool(re.match(pattern, sku.strip()))


def validate_price(price: float | None) -> bool:
    """Validate price is within reasonable range.

    Args:
        price: Price value to validate

    Returns:
        True if price is valid
    """
    if price is None:
        return False
    return 0 < price < 100000


def write_json_atomic(data: dict[str, Any], output_path: str) -> None:
    """Write JSON data to file atomically using temp file + rename.

    Args:
        data: Data to write
        output_path: Destination file path
    """
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Write to temp file first
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output_dir, delete=False, suffix=".tmp"
    ) as tmp_file:
        json.dump(data, tmp_file, indent=2, ensure_ascii=False)
        tmp_path = tmp_file.name

    # Atomic rename
    try:
        os.replace(tmp_path, output_path)
        logger.info(f"Wrote JSON to {output_path}")
    except Exception as e:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise RuntimeError(f"Failed to write JSON to {output_path}: {e}")


class ParsingStats:
    """Track parsing statistics for summary reporting."""

    def __init__(self):
        self.products_parsed = 0
        self.variants_parsed = 0
        self.errors = 0
        self.warnings = 0
        self.skipped_products = []

    def add_product(self, base_sku: str, variant_count: int):
        """Record a successfully parsed product."""
        self.products_parsed += 1
        self.variants_parsed += variant_count

    def add_error(self, message: str):
        """Record an error."""
        self.errors += 1
        logger.error(message)

    def add_warning(self, message: str):
        """Record a warning."""
        self.warnings += 1
        logger.warning(message)

    def skip_product(self, base_sku: str, reason: str):
        """Record a skipped product."""
        self.skipped_products.append((base_sku, reason))
        logger.warning(f"Skipped product {base_sku}: {reason}")

    def print_summary(self):
        """Print parsing summary report."""
        logger.info("=" * 60)
        logger.info("PARSING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Products parsed: {self.products_parsed}")
        logger.info(f"Variants parsed: {self.variants_parsed}")
        logger.info(f"Errors: {self.errors}")
        logger.info(f"Warnings: {self.warnings}")

        if self.skipped_products:
            logger.info(f"\nSkipped products ({len(self.skipped_products)}):")
            for sku, reason in self.skipped_products[:10]:  # Show first 10
                logger.info(f"  - {sku}: {reason}")
            if len(self.skipped_products) > 10:
                logger.info(f"  ... and {len(self.skipped_products) - 10} more")

        logger.info("=" * 60)
