"""Pure functions for parsing product attributes from HTML content.

Following CLAUDE.md: testable, composable functions with no side effects.
"""

import re
from typing import Optional


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


def parse_weight_from_text(text: str) -> Optional[str]:
    """Extract weight from text content.

    Args:
        text: Text containing weight info (e.g., "Net weight: 0.22 kg")

    Returns:
        Weight string (e.g., "0.22 kg") or None
    """
    if not text:
        return None

    match = re.search(r"Net weight:\s*([\d.]+\s*kg)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


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
