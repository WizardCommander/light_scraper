"""Pure functions for parsing product attributes from HTML content.

Following CLAUDE.md: testable, composable functions with no side effects.
"""

import re
from typing import Optional

from loguru import logger


CERTIFICATION_PATTERNS = [
    (r"IP\s*(\d{2})", "IP Rating"),
    (r"(\d{2,3}[-–]\d{2,3}\s*V)", "Voltage"),
    (r"\b(CE)\b", "Certification"),
]


def parse_designer_from_title(title: str) -> Optional[str]:
    """Extract designer name from product title.

    Args:
        title: Product title text (e.g., "Kelly, design by Andrea Tosetto, 2015")

    Returns:
        Designer name or None if not found
    """
    if not title or "design by" not in title.lower():
        return None

    match = re.search(r"design by\s+([^,]+)", title, flags=re.IGNORECASE)
    if not match:
        return None

    designer_name = match.group(1).strip()
    designer_name = re.sub(r",?\s*\d{4}$", "", designer_name).strip()

    return designer_name if designer_name else None


def parse_table_header_attributes(header_texts: list[str]) -> dict[str, str]:
    """Parse attribute key-value pairs from table header texts.

    Args:
        header_texts: List of header cell texts (e.g., ["Structure: Metal", "Light source"])

    Returns:
        Dictionary of parsed attributes
    """
    attributes = {}

    for header_text in header_texts:
        if not header_text or not header_text.strip():
            continue

        header_text = header_text.strip()

        if ":" in header_text and header_text not in ["Code 2700 K", "Code 3000 K"]:
            parts = header_text.split(":", 1)
            key = parts[0].strip()
            value = parts[1].strip()
            if key and value:
                attributes[key] = value

    return attributes


def clean_variant_header_name(header_text: str) -> str:
    """Clean variant table header to extract just the attribute name.

    Handles headers like "Diffusore: Vetro" -> "Diffusore"
    Filters out variant product names that look like "Kelly medium dome 60"

    Args:
        header_text: Raw header text from table

    Returns:
        Cleaned attribute name, or empty string if header should be ignored
    """
    if not header_text:
        return ""

    header_text = header_text.strip()

    # Filter out headers that look like variant names/codes
    # These typically contain product names or numbers followed by size/model info
    invalid_patterns = [
        r"^[A-Z][\w\-]+\s+(small|medium|large|mini|dome|pendant|suspension).*\d+$",  # e.g., "Kelly medium dome 60", "A-Tube small pendant 40"
        r"^\d{5,}",  # Long product codes like "14127"
    ]

    for pattern in invalid_patterns:
        if re.match(pattern, header_text):
            return ""  # Ignore this header

    # If header contains colon, extract only the attribute name (before colon)
    if ":" in header_text:
        # Split on first colon and take the left part
        attribute_name = header_text.split(":", 1)[0].strip()
        return attribute_name

    # Otherwise return as-is
    return header_text


def parse_weight_from_text(text: str) -> Optional[str]:
    """Extract weight from text content (multilingual).

    Args:
        text: Text containing weight info in various languages:
              - English: "Net weight: 0.22 kg"
              - German: "Nettogewicht: 0,40 kg"
              - Italian: "Peso netto: 6.00 kg"

    Returns:
        Weight string normalized to format "0.22 kg" or None
    """
    if not text:
        return None

    # Match multiple languages
    # English: Net weight, German: Nettogewicht, Italian: Peso netto
    # Allow both decimal separators: . and ,
    match = re.search(
        r"(?:Net\s*weight|Nettogewicht|Peso\s*netto):\s*([\d,\.]+)\s*kg",
        text,
        re.IGNORECASE,
    )
    if match:
        weight_str = match.group(1).strip()
        # Normalize comma to decimal point
        weight_str = weight_str.replace(",", ".")
        return f"{weight_str} kg"

    logger.debug(f"Failed to parse weight from text: {text[:100]}")
    return None


def parse_weight_to_float(weight_str: str) -> Optional[float]:
    """Convert weight string to float in kg.

    Args:
        weight_str: Weight string like "0.40 kg" or "1.2 kg"

    Returns:
        Weight as float (kg) or None if parsing fails
    """
    if not weight_str:
        return None

    # Extract just the number part
    match = re.search(r"([\d.]+)", weight_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            logger.warning(f"Failed to convert weight to float: {weight_str}")
            return None

    logger.debug(f"No numeric pattern found in weight string: {weight_str}")
    return None


def parse_hills_from_text(text: str) -> Optional[str]:
    """Extract hills count from text content.

    Args:
        text: Text containing hills info (e.g., "Hills: 2")

    Returns:
        Hills count as string or None
    """
    if not text:
        return None

    match = re.search(r"Hills:\s*(\d+)", text)
    return match.group(1).strip() if match else None


def extract_certifications_from_html(html: str) -> dict[str, str]:
    """Extract certification badges from HTML content.

    Args:
        html: HTML content to search

    Returns:
        Dictionary of certification attributes
    """
    certifications = {}

    for pattern, attr_name in CERTIFICATION_PATTERNS:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            certifications[attr_name] = match.group(1).strip()

    return certifications
