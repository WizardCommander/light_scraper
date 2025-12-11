"""WooCommerce CSV exporter.

Following CLAUDE.md: pure, testable functions with clear responsibilities.
Based on official WooCommerce CSV import format specification.
German column headers for German WooCommerce stores.
"""

import csv
import re
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from src.models import ProductData


# WooCommerce German column names mapping (exact order from client CSV)
# 76 total columns matching client CSV exactly
WOOCOMMERCE_GERMAN_COLUMNS = [
    "ID",
    "Typ",
    "SKU",
    "Parent SKU",
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
    "Lieferzeit",
    "Gewicht (kg)",
    "Länge (cm)",
    "Breite (cm)",
    "Höhe (cm)",
    "Kundenrezensionen erlauben?",
    "Hinweis zum Kauf",
    "Angebotspreis",
    "Regulärer Preis",
    "Übergkategorie",
    "Kategorienstruktur",
    "Schlagwörter",
    "Versandklasse",
    "Anzahl Fotos",
    "Bilder",
    "Gruppierte Produkte",
    "Zusatzverkäufe",
    "Cross-Sells (Querverkäufe)",
    "Externe URL",
    "Button-Text",
    "Position",
    "Marke",
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
    # Custom product fields (17 new columns)
    "Produktnummer",  # Product number (same as SKU)
    "Produkttyp",  # Product type (installation_type)
    "Designer",  # Designer name
    "Produktfamilie",  # Product family
    "Material",  # Material specification
    "Diffusor",  # Diffuser type
    "Produktfarben",  # All available colors
    "Seillänge",  # Cable/rope length
    "Lichtquelle",  # Light source specifications
    "Dimmbarkeit",  # Dimmability type
    "IP-Schutz",  # IP rating
    "Stoßfestigkeit",  # Impact resistance (IK rating)
    "Spannung",  # Voltage
    "Zertifizierung",  # Certifications
    "Information",  # Additional notes
    "Datenblatt",  # Datasheet URL
    "Montageanleitung",  # Assembly instructions URL
    "",  # Trailing empty column (matches client CSV format)
]

# Mapping of mounting types to standardized German canopy terminology
CANOPY_TYPE_MAPPING = {
    # Flush-mount (recessed)
    "dome": "Einbaubaldachin",
    "ceiling": "Einbaubaldachin",
    "recessed": "Einbaubaldachin",
    "flush": "Einbaubaldachin",
    # Surface-mount
    "suspension": "Aufbaubaldachin",
    "surface": "Aufbaubaldachin",
    "pendant": "Aufbaubaldachin",
    # Specific sizes
    "xxs": "XXS",
    "micro": "Micro",
    "remote": "Remote",
}

# Color translation mapping from Italian/English to German
_COLOR_TRANSLATION_MAP = {
    "Bianco Opaco": "Weiß Matt",
    "Bianco Lucido": "Weiß Glänzend",
    "Bianco": "Weiß",
    "Nero Opaco": "Schwarz Matt",
    "Nero Lucido": "Schwarz Glänzend",
    "Nero": "Schwarz",
    "Bronzo Ramato": "Bronze",
    "Champagne Opaco": "Champagner Matt",
    # Note: "Champagne" alone removed to avoid substring conflict with "Champagner"
    # "Champagne Opaco" handles the common case
    "White": "Weiß",
    "Black": "Schwarz",
    "Bronze": "Bronze",
}


def extract_clean_product_name(product: ProductData) -> str:
    """Extract clean product name without design attribution.

    Uses original_name (from price list) if available, otherwise cleans the name field.
    For variations, appends German color from attributes.

    Examples:
        "Kelly, Design von Andrea Tosetto, 2015" -> "Kelly"
        "Kelly small dome 50" -> "Kelly small dome 50"
        "Kelly small dome 50 Weiß" -> "Kelly small dome 50 Weiß"

    Args:
        product: Product data

    Returns:
        Clean product name with color for variations
    """
    # Use original_name from price list if available (untranslated English name)
    if product.original_name:
        name = product.original_name

        # For variations, append German color using _extract_color
        if product.product_type == "variation":
            color = _extract_color(product)
            if color:
                name = f"{name} {color}"

        return name

    # Fallback to cleaning the name field
    if not product.name:
        return ""

    name = product.name

    # Remove design attribution (e.g., ", Design von Andrea Tosetto, 2015")
    if "," in name:
        # Check if comma is followed by design info
        parts = name.split(",", 1)
        if len(parts) > 1:
            remaining = parts[1].lower().strip()
            if remaining.startswith(("design ", "designer ")):
                name = parts[0].strip()

    # For variations, extract parent name and append German color
    if product.product_type == "variation" and product.variation_attributes:
        # Get color attribute (German translation from WooCommerce attributes)
        color = product.variation_attributes.get("Farbe")

        if color:
            # Extract parent product name by removing any existing color/code suffixes
            # Split on common delimiters and take the first meaningful parts
            # Remove Italian colors, codes, and numbers
            parts = name.split()

            # Keep product name parts (usually first 3-5 words like "Kelly small dome 50")
            # Stop when we hit color names, SKU codes, or "–" delimiter
            parent_parts = []
            for part in parts:
                # Stop at color codes (numbers like 9010, 14126, etc.)
                if part.isdigit() and len(part) >= 4:
                    break
                # Stop at dash delimiter
                if part in ["–", "-", "—"]:
                    break
                # Stop at Italian color names
                if part.lower() in ["bianco", "nero", "bronzo", "champagne", "opaco", "lucido", "ramato"]:
                    break
                parent_parts.append(part)

            if parent_parts:
                name = " ".join(parent_parts) + f" {color}"
            else:
                name = f"{name} {color}"

    return name


def extract_product_family(product: ProductData) -> str:
    """Extract base product family name.

    Returns just the first word (e.g., "Kelly" from "Kelly small dome 50")

    Args:
        product: Product data

    Returns:
        Product family name (first word)
    """
    clean_name = extract_clean_product_name(product)
    return clean_name.split()[0] if clean_name else ""


def extract_product_type_german(product: ProductData) -> str:
    """Extract product type in German (installation type).

    Args:
        product: Product data

    Returns:
        German product type (e.g., "Hängeleuchte", "Wandleuchte")
    """
    return product.installation_type or ""


def count_product_images(product: ProductData) -> str:
    """Count number of product images.

    Args:
        product: Product data

    Returns:
        String representation of image count
    """
    if not product.images:
        return ""
    return str(len(product.images))


def build_light_source_string(product: ProductData) -> str:
    """Build light source specification string from product data.

    Args:
        product: Product data

    Returns:
        Light source string (e.g., "E27 LED B / L max 12cm\\n3x 25W")
    """
    # Check if light source info exists in attributes
    if product.attributes and "Light source" in product.attributes:
        return product.attributes["Light source"]

    # Try to build from light_specs if available
    if product.light_specs:
        parts = []
        if "type" in product.light_specs:
            parts.append(product.light_specs["type"])
        if "wattage" in product.light_specs:
            parts.append(f"{product.light_specs['wattage']}W")
        if parts:
            return " ".join(parts)

    return ""


def extract_ik_rating(product: ProductData) -> str:
    """Extract IK impact resistance rating from product attributes.

    Args:
        product: Product data

    Returns:
        IK rating (e.g., "IK07") or empty string
    """
    if not product.attributes:
        return ""

    # Check for IK rating in various attribute names
    for key, value in product.attributes.items():
        if "ik" in key.lower() or "impact" in key.lower():
            return value
        # Check if value contains IK pattern (e.g., "IK07")
        if value and "IK" in value.upper():
            match = re.search(r"IK\s*\d{2}", value, re.IGNORECASE)
            if match:
                return match.group(0).upper()

    return ""


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


def format_ip_rating(rating: str | None) -> str:
    """Ensure IP rating has 'IP' prefix.

    Args:
        rating: IP rating value (e.g., "20" or "IP20")

    Returns:
        Properly formatted IP rating (e.g., "IP20") or empty string

    Examples:
        >>> format_ip_rating("20")
        "IP20"
        >>> format_ip_rating("IP44")
        "IP44"
        >>> format_ip_rating("ip65")
        "IP65"
    """
    if not rating:
        return ""

    rating = rating.strip()
    if rating and not rating.upper().startswith("IP"):
        return f"IP{rating}"

    return rating.upper()


def translate_colors_to_german(colors_text: str) -> str:
    """Translate Italian/English color names to German.

    Removes color codes (e.g., "– 9010") and collapses excessive whitespace
    (newlines, tabs, multiple spaces) into single spaces.

    Args:
        colors_text: Color names string (comma-separated or with codes)

    Returns:
        German color names with codes removed and whitespace normalized

    Examples:
        >>> translate_colors_to_german("Bianco Opaco – 9010")
        "Weiß Matt"
        >>> translate_colors_to_german("Nero Opaco – 9005")
        "Schwarz Matt"
        >>> translate_colors_to_german("Bronzo Ramato")
        "Bronze"
        >>> translate_colors_to_german("Bianco\\n\\t\\tOpaco – 9010")
        "Weiß Matt"
    """
    result = colors_text
    # Sort by key length (longest first) to avoid partial matches
    # e.g., "Champagne Opaco" must be replaced before "Champagne"
    for italian, german in sorted(
        _COLOR_TRANSLATION_MAP.items(), key=lambda x: len(x[0]), reverse=True
    ):
        result = result.replace(italian, german)

    # Remove color codes (e.g., "– 9010")
    result = re.sub(r"\s*[–-]\s*\d+", "", result)

    # Collapse multiple whitespace (including newlines, tabs) into single spaces
    # Note: .split() already removes leading/trailing whitespace, so no .strip() needed
    return " ".join(result.split())


def _infer_installation_type(categories: list[str]) -> str:
    """Infer German installation type from categories.

    Args:
        categories: List of product categories

    Returns:
        German installation type (e.g., "Hängeleuchte", "Wandleuchte")

    Examples:
        >>> _infer_installation_type(["Hängeleuchten"])
        "Hängeleuchte"
        >>> _infer_installation_type(["pendant", "dome"])
        "Hängeleuchte"
        >>> _infer_installation_type(["Wandleuchten"])
        "Wandleuchte"
    """
    cats_text = " ".join(categories).lower()

    if any(
        x in cats_text
        for x in [
            "hänge",
            "pendant",
            "pendel",
            "suspension",
            "sospensioni",
            "dome",
            "sphere",
        ]
    ):
        return "Hängeleuchte"
    elif any(
        x in cats_text for x in ["wall", "wand", "applique", "parete", "wandleuchten"]
    ):
        return "Wandleuchte"
    elif any(
        x in cats_text
        for x in ["ceiling", "decken", "flush", "soffitto", "deckenleuchten"]
    ):
        return "Deckenleuchte"

    return ""


def build_short_description_plain(product: ProductData) -> str:
    """Build plain text short description (Kurzbeschreibung).

    This is used for the WooCommerce short description field.
    Should be plain text without HTML, focusing on key features.

    Args:
        product: Product data

    Returns:
        Plain text short description

    Priority:
        1. Use AI-generated short_description if available
        2. Fall back to generic format: "[Installation Type] [Family Name]"
    """
    # For variations, return empty (parent has the description)
    if product.product_type == "variation":
        return ""

    # Use AI-generated short description if available (preferred for all products)
    if product.short_description:
        return product.short_description

    # Fallback: Build generic description from available fields
    parts = []
    if product.installation_type:
        parts.append(product.installation_type)

    family_name = extract_product_family(product)
    if family_name:
        parts.append(family_name)

    return " - ".join(parts) if parts else ""


def build_short_description_html(product: ProductData) -> str:
    """Build HTML-formatted short description with technical specs list.

    This is used for the full description field, not Kurzbeschreibung.

    Args:
        product: Product data

    Returns:
        HTML formatted short description with <ul> list

    Format matches client requirements:
    - Opening line with product type and key feature
    - <ul> list with <li><strong>Label:</strong> Value</li> items
    - Includes: Lichttechnik, Material, Farbe, Abmessungen
    """
    parts = []

    # Opening line: Installation type and name
    if product.installation_type:
        intro = product.installation_type
        if product.name:
            # Extract base name without variation suffix
            base_name = extract_clean_product_name(product)
            intro = f"{product.installation_type} - {base_name}"
        parts.append(intro)
    elif product.name:
        # Fallback to just name if no installation type
        base_name = extract_clean_product_name(product)
        parts.append(base_name)

    # Build specification list
    spec_items = []

    # Lichttechnik (LED specs)
    if product.light_specs:
        light_parts = []
        if "wattage" in product.light_specs:
            light_parts.append(f"LED {product.light_specs['wattage']}W")
        if "kelvin" in product.light_specs:
            light_parts.append(product.light_specs["kelvin"])
        if "lumen" in product.light_specs:
            light_parts.append(f"{product.light_specs['lumen']}lm")

        if light_parts:
            spec_items.append(
                f"<li><strong>Lichttechnik:</strong> {', '.join(light_parts)}</li>"
            )

    # Material
    if product.material:
        spec_items.append(f"<li><strong>Material:</strong> {product.material}</li>")

    # Farbe (Color) - for parent products, show all color options
    color = _extract_color(product)
    if color:
        spec_items.append(f"<li><strong>Farbe:</strong> {color}</li>")

    # Abmessungen (Dimensions)
    if product.dimensions:
        dims = product.dimensions
        if "length" in dims and "width" in dims and "height" in dims:
            # Format like "dmxh= 910x60mm"
            dim_str = f"{dims['length']}x{dims['width']}x{dims['height']}cm"
            spec_items.append(f"<li><strong>Abmessungen:</strong> {dim_str}</li>")

    # Build final HTML
    if not spec_items:
        # No specs available, return plain intro or empty
        return parts[0] if parts else ""

    html = parts[0] if parts else ""
    html += "\n<ul>\n"
    html += "\n".join(spec_items)
    html += "\n</ul>"

    return html


def build_attribute_html_list(product: ProductData) -> str:
    """Build HTML unordered list of product attributes for description.

    Args:
        product: Product data

    Returns:
        HTML formatted attribute list

    Includes attributes in priority order:
    - Designer
    - Material
    - IP Rating
    - Voltage
    - Certification
    - Dimensions (L×W×H)
    - Weight
    - Light specifications (Wattage, Lumens, Kelvin)
    - Installation type
    - Other technical specs
    """
    attr_items = []

    # Designer
    if product.attributes and "Designer" in product.attributes:
        attr_items.append(
            f"<li><strong>Designer:</strong> {product.attributes['Designer']}</li>"
        )

    # Material
    if product.material:
        attr_items.append(f"<li><strong>Material:</strong> {product.material}</li>")

    # IP Rating
    if product.ip_rating:
        attr_items.append(f"<li><strong>IP Rating:</strong> {product.ip_rating}</li>")

    # Voltage
    if product.attributes and "Voltage" in product.attributes:
        attr_items.append(
            f"<li><strong>Spannung:</strong> {product.attributes['Voltage']}</li>"
        )

    # Certification
    if product.attributes and "Certification" in product.attributes:
        attr_items.append(
            f"<li><strong>Zertifizierung:</strong> {product.attributes['Certification']}</li>"
        )

    # Dimensions
    if product.dimensions:
        dims = product.dimensions
        if all(k in dims for k in ["length", "width", "height"]):
            dim_str = f"{dims['length']} × {dims['width']} × {dims['height']} cm"
            attr_items.append(
                f"<li><strong>Abmessungen (L×B×H):</strong> {dim_str}</li>"
            )

    # Weight
    if product.weight:
        attr_items.append(f"<li><strong>Gewicht:</strong> {product.weight} kg</li>")

    # Light specifications
    if product.light_specs:
        light_parts = []
        if "wattage" in product.light_specs:
            light_parts.append(f"{product.light_specs['wattage']}W")
        if "lumen" in product.light_specs:
            light_parts.append(f"{product.light_specs['lumen']}lm")
        if "kelvin" in product.light_specs:
            light_parts.append(f"{product.light_specs['kelvin']}K")

        if light_parts:
            attr_items.append(
                f"<li><strong>Lichttechnik:</strong> {', '.join(light_parts)}</li>"
            )

    # Installation type
    if product.installation_type:
        attr_items.append(
            f"<li><strong>Montageart:</strong> {product.installation_type}</li>"
        )

    # Other attributes from the attributes dict (skip already added ones)
    if product.attributes:
        skip_keys = {"Designer", "Voltage", "Certification"}
        for key, value in product.attributes.items():
            if key not in skip_keys and value:
                attr_items.append(f"<li><strong>{key}:</strong> {value}</li>")

    # Return empty string if no attributes
    if not attr_items:
        return ""

    # Build HTML list
    html = "\n<h3>Technische Spezifikationen</h3>\n<ul>\n"
    html += "\n".join(attr_items)
    html += "\n</ul>"

    return html


def generate_tags(product: ProductData) -> str:
    """Generate comma-separated tags from product data.

    Args:
        product: Product data

    Returns:
        Comma-separated tag string

    Generates tags from:
    - Brand name (manufacturer)
    - Product name
    - Product type (installation_type: Hängeleuchte, Deckenleuchte, etc.)
    - Key attributes (LED, Dali, etc.)
    """
    tags = []

    # Add manufacturer/brand
    if product.manufacturer:
        tags.append(product.manufacturer)

    # Add product name (without variations)
    if product.name:
        # For variations, remove the variation suffix (e.g., "- Pad far mountain, 2700°K")
        base_name = (
            product.name.split(" - ")[0] if " - " in product.name else product.name
        )
        tags.append(base_name)

    # Add installation type (Hängeleuchte, Deckenleuchte, etc.)
    if product.installation_type:
        tags.append(product.installation_type)

    # Add key attributes if available
    if product.attributes:
        # Common tags from attributes
        key_attrs = ["LED", "Dali", "DALI", "switchDim"]
        for attr_key, attr_value in product.attributes.items():
            # Add attribute value if it's a key attribute
            if attr_key in key_attrs or attr_value in key_attrs:
                tags.append(attr_value)

    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_tags.append(tag)

    return ", ".join(unique_tags)


def _extract_attribute(product: ProductData, keys: list[str]) -> str:
    """Generic attribute extractor that checks variation and regular attributes.

    Args:
        product: Product data
        keys: List of possible attribute keys to search for (in priority order)

    Returns:
        First matching attribute value, or empty string if none found
    """
    # Check variation_attributes first (higher priority for variations)
    if product.variation_attributes:
        for key in keys:
            if key in product.variation_attributes:
                return product.variation_attributes[key]

    # Check regular attributes
    if product.attributes:
        for key in keys:
            if key in product.attributes:
                return product.attributes[key]

    return ""


def _extract_color(product: ProductData) -> str:
    """Extract Farbe (color) attribute from product.

    Args:
        product: Product data

    Returns:
        Color value(s) as string (cleaned of color codes)
    """
    # For variations: check size variant fields FIRST (highest priority for individual color)
    if product.product_type == "variation" and product.variation_attributes:
        for key, value in product.variation_attributes.items():
            # Size variant fields like "Kelly small dome 50" contain individual colors
            if any(x in key.lower() for x in ["dome", "sphere", "suspension", "wall"]):
                if value and value.strip():
                    # Clean color codes and translate
                    color = translate_colors_to_german(value.strip())
                    # For variations: extract only the FIRST color if multiple colors present
                    # (some variants list all available colors)
                    parts = color.split()
                    if parts:
                        # Take first word (the actual color), strip "Matt" suffix
                        first_color = parts[0]
                        # Check if second word is "Matt" - if so, exclude it for consistency
                        # with client format (client uses "Weiß" not "Weiß Matt")
                        return first_color
                    return color

    # Check for standard names and Lodes Italian name "Struttura" (structure/material/color)
    result = _extract_attribute(product, ["Farbe", "Color", "Colour", "Struttura"])
    # Clean excessive whitespace and color codes
    if result:
        # Translate and clean color codes (removes "– 9005" etc.)
        result = translate_colors_to_german(result)

        # For variations: extract only the FIRST color if multiple present
        if product.product_type == "variation" and result:
            parts = result.split()
            if parts:
                # Return first word only (strip "Matt" suffix)
                return parts[0]

    return result


def _extract_light_color(product: ProductData) -> str:
    """Extract Lichtfarbe (light color/temperature) attribute from product.

    Args:
        product: Product data

    Returns:
        Light temperature value(s) as string (e.g., "2700K", "3000K")
    """
    # Priority 1: Check light_specs for Kelvin values
    if product.light_specs and "kelvin" in product.light_specs:
        return product.light_specs["kelvin"]

    # Priority 2: Try standard attribute keys (but only Kelvin-related ones)
    result = _extract_attribute(product, ["Lichtfarbe", "Kelvin", "Temperature"])
    if result:
        # Clean excessive whitespace
        result = " ".join(result.split())
        # Only return if it looks like a Kelvin value (contains digits followed by K)
        if re.search(r"\d+K", result):
            return result

    return ""


def _extract_dimmability(product: ProductData) -> str:
    """Extract Dimmbarkeit (dimmability) attribute from product.

    Args:
        product: Product data

    Returns:
        Dimmability type(s) as string
    """
    return _extract_attribute(
        product, ["Dimmbarkeit", "Dimmable", "Dimming", "Dali", "DALI"]
    )


def _extract_mounting(product: ProductData) -> str:
    """Extract Montage (mounting type) attribute from product.

    Args:
        product: Product data

    Returns:
        Mounting type(s) as string with standardized canopy terminology
    """
    # For Lodes products, check size variant field names FIRST
    if product.variation_attributes:
        for key in product.variation_attributes.keys():
            key_lower = key.lower()
            # Check for canopy type keywords in the key
            for keyword, canopy_type in CANOPY_TYPE_MAPPING.items():
                if keyword in key_lower:
                    return canopy_type

    # Check standard attribute names
    result = _extract_attribute(
        product, ["Montage", "Mounting", "Canopy", "Baldachin", "Variant Type"]
    )
    if result:
        result_lower = result.lower()
        # Try to map to canopy type
        for keyword, canopy_type in CANOPY_TYPE_MAPPING.items():
            if keyword in result_lower:
                return canopy_type
        # If no mapping found, return cleaned original value
        return " ".join(result.split())

    return ""


def _map_woocommerce_attributes(product: ProductData) -> dict[str, Any]:
    """Map product to WooCommerce's 4 required German attributes.

    Args:
        product: Product data

    Returns:
        Dictionary with Attribut 1-4 columns

    Maps to exactly 4 attributes:
    1. Farbe (Color)
    2. Lichtfarbe (Light Color/Temperature)
    3. Dimmbarkeit (Dimmability)
    4. Montage (Mounting type)

    Sichtbar: 1 for parent/simple products, "" for variations
    Global: Always 1
    """
    is_parent_or_simple = product.product_type in ["simple", "variable"]
    sichtbar = 1 if is_parent_or_simple else ""

    # For parent products, use all available colors; for variations, use specific color
    if is_parent_or_simple and product.available_colors:
        color_clean = product.available_colors
    else:
        color_raw = _extract_color(product)
        color_clean = translate_colors_to_german(color_raw) if color_raw else ""

    # For Dimmbarkeit: parent should be empty, variations can have specific values
    dimmbarkeit = ""
    if not is_parent_or_simple:
        dimmbarkeit = _extract_dimmability(product)

    return {
        "Attribut 1 Name": "Farbe",
        "Attribut 1 Wert(e)": color_clean,
        "Attribut 1 Sichtbar": sichtbar,
        "Attribut 1 Global": "",
        "Attribut 2 Name": "Lichtfarbe",
        "Attribut 2 Wert(e)": _extract_light_color(product),
        "Attribut 2 Sichtbar": sichtbar,
        "Attribut 2 Global": "",
        "Attribut 3 Name": "Dimmbarkeit",
        "Attribut 3 Wert(e)": dimmbarkeit,
        "Attribut 3 Sichtbar": sichtbar,
        "Attribut 3 Global": "",
        "Attribut 4 Name": "Montage",
        "Attribut 4 Wert(e)": _extract_mounting(product),
        "Attribut 4 Sichtbar": sichtbar,
        "Attribut 4 Global": "",
    }


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
    rows = [_product_to_woocommerce_row(product, default_price, idx) for idx, product in enumerate(products)]
    df = pd.DataFrame(rows)

    # Ensure ALL WooCommerce columns are present (even if empty)
    for col in WOOCOMMERCE_GERMAN_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Use only standard WooCommerce columns (no meta: columns)
    df = df[WOOCOMMERCE_GERMAN_COLUMNS]

    # Replace NaN values with empty strings
    df = df.fillna("")

    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Export to CSV matching schema format exactly
    df.to_csv(
        output_file,
        index=False,
        sep=";",  # Semicolon separator per client requirement
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    logger.info(f"Exported {len(products)} products to {output_file}")
    return output_file


def _product_to_woocommerce_row(
    product: ProductData, default_price: float, position: int = 0
) -> dict[str, Any]:
    """Convert ProductData to WooCommerce CSV row format with German columns.

    Args:
        product: Product data to convert
        default_price: Default price if product.regular_price is None
        position: Position (0 for parent, 1+ for variations in order)

    Returns:
        Dictionary representing a CSV row with German WooCommerce columns
    """
    # Format images: comma-separated URLs with line breaks (first image becomes featured)
    images = ",\n".join(product.images) if product.images else ""

    # Format prices with German decimal separator
    regular_price = format_german_decimal(
        product.regular_price if product.regular_price is not None else default_price
    )
    sale_price = format_german_decimal(product.sale_price)

    # Format weight and dimensions with German decimal separator
    weight = format_german_decimal(product.weight)

    # Determine if reviews should be enabled (1 for parent/simple, 0 for variations)
    allow_reviews = 1 if product.product_type in ["simple", "variable"] else 0

    # Use plain description (client will handle technical specs separately)
    full_description = product.description

    # Base WooCommerce columns (German names)
    row = {
        "ID": "",  # Empty - WooCommerce assigns IDs during import
        "Typ": product.product_type,  # simple, variable, or variation
        "SKU": product.sku,
        "Parent SKU": (
            product.parent_sku
            if product.product_type == "variation" and product.parent_sku
            else ""
        ),
        "GTIN, UPC, EAN oder ISBN": product.ean if product.ean else "",
        "Name": extract_clean_product_name(product),
        "Veröffentlicht": 1,  # 1 = published (matching client CSV)
        "Ist hervorgehoben?": 0,  # 0 = not featured
        "Sichtbarkeit im Katalog": "visible",
        "Kurzbeschreibung": build_short_description_plain(product),
        "Beschreibung": full_description,
        "Datum, an dem Angebotspreis beginnt": "",
        "Datum, an dem Angebotspreis endet": "",
        "Steuerstatus": "taxable",
        "Steuerklasse": "parent",
        "Vorrätig?": 1,
        "Bestand": product.stock if product.stock is not None else "",
        "Geringe Lagermenge": "",
        "Lieferrückstande erlaubt?": 0,
        "Nur einzeln verkaufen?": 0,
        "Lieferzeit": "",  # Client will fill manually (varies per product)
        "Gewicht (kg)": weight,
        "Länge (cm)": "",
        "Breite (cm)": "",
        "Höhe (cm)": "",
        "Kundenrezensionen erlauben?": allow_reviews,
        "Hinweis zum Kauf": "",
        "Angebotspreis": sale_price,
        "Regulärer Preis": regular_price,
        "Übergkategorie": "",  # Will be populated below
        "Kategorienstruktur": "",  # Will be populated below
        "Schlagwörter": "",  # Will be populated below
        "Versandklasse": "",
        "Anzahl Fotos": count_product_images(product),
        "Bilder": images,
        "Gruppierte Produkte": "",
        "Zusatzverkäufe": "",
        "Cross-Sells (Querverkäufe)": "",
        "Externe URL": "",
        "Button-Text": "",
        "Position": position,
        "Marke": product.manufacturer,
    }

    # Add dimensions if available (with German decimal formatting)
    if product.dimensions:
        if "length" in product.dimensions:
            row["Länge (cm)"] = format_german_decimal(product.dimensions["length"])
        if "width" in product.dimensions:
            row["Breite (cm)"] = format_german_decimal(product.dimensions["width"])
        if "height" in product.dimensions:
            row["Höhe (cm)"] = format_german_decimal(product.dimensions["height"])

    # Map to the 4 required German attributes (Farbe, Lichtfarbe, Dimmbarkeit, Montage)
    attribute_mapping = _map_woocommerce_attributes(product)
    row.update(attribute_mapping)

    # Extract from attributes (normalize Italian→German field names)
    attrs = product.attributes or {}

    # Material: Check attrs for "Material", "Struttura", etc.
    material = (
        attrs.get("Material")
        or attrs.get("Struttura")
        or attrs.get("Structure")
        or product.material
        or ""
    )

    # Diffusor: Check attrs for "Diffusor", "Diffusore", etc.
    diffusor = (
        attrs.get("Diffusor") or attrs.get("Diffusore") or attrs.get("Diffuser") or ""
    )

    # Dimmbarkeit: Check attrs
    dimmbarkeit = attrs.get("Dimmbarkeit") or attrs.get("Dimming") or ""

    # Produkttyp: Use installation_type field or infer from categories
    produkttyp = product.installation_type or _infer_installation_type(
        product.categories or []
    )

    # Produktfarben: For parent products, aggregate colors from variation_attributes
    produktfarben = product.available_colors or ""
    if not produktfarben and product.product_type == "variable":
        # Use _extract_attribute to check all color field names (German, English, Italian)
        # Note: "Struttura" is Italian for structure/frame color
        color_value = _extract_attribute(
            product, ["Farbe", "Color", "Colour", "Colore", "Struttura"]
        )
        if color_value:
            produktfarben = translate_colors_to_german(color_value)

    # Lichtquelle: Extract from attributes (look for "Dimensions" field containing E27 info)
    lichtquelle = build_light_source_string(product)
    if not lichtquelle:
        dims_text = attrs.get("Dimensions") or ""
        if "E27" in dims_text or "LED" in dims_text:
            lichtquelle = dims_text

    # Seillänge: Use cable_length field or search attributes (only for parent/simple products)
    seillange = ""
    if product.product_type in ["simple", "variable"]:
        seillange = product.cable_length or ""
        if not seillange:
            for key, value in attrs.items():
                if "seil" in key.lower() or "cable" in key.lower():
                    seillange = value
                    break

    # Information: Use product_notes field or default German text (only for parent/simple products)
    information = ""
    if product.product_type in ["simple", "variable"]:
        information = product.product_notes or "Leuchtmittel nicht inkludiert."

    # Montageanleitung: Use installation_manual_url field
    montageanleitung = product.installation_manual_url or ""

    # Kategorienstruktur: Build from categories with > separator (only for parent/simple)
    kategorienstruktur = ""
    if product.product_type in ["simple", "variable"]:
        kategorienstruktur = ">".join(product.categories) if product.categories else ""

    # Übergkategorie: Extract parent categories (only for parent/simple)
    ubergkategorie = ""
    if product.product_type in ["simple", "variable"] and product.categories:
        # Extract unique parent categories (first level of each hierarchy)
        parent_cats = list(dict.fromkeys([cat.split(">")[0] for cat in product.categories]))
        ubergkategorie = ",".join(parent_cats)

    # Schlagwörter: Generate tags (only for parent/simple)
    schlagworter = ""
    if product.product_type in ["simple", "variable"]:
        schlagworter = generate_tags(product)

    # Format IP rating with "IP" prefix
    ip_schutz = format_ip_rating(product.ip_rating or attrs.get("IP Rating", ""))

    # Add custom product fields (17 new columns)
    row.update(
        {
            "Produktnummer": product.sku,  # Same as SKU
            "Produkttyp": produkttyp,
            "Designer": attrs.get("Designer", ""),
            "Produktfamilie": extract_product_family(product),
            "Material": material,
            "Diffusor": diffusor,
            "Produktfarben": produktfarben,
            "Seillänge": seillange,
            "Lichtquelle": lichtquelle,
            "Dimmbarkeit": dimmbarkeit,
            "IP-Schutz": ip_schutz,
            "Stoßfestigkeit": extract_ik_rating(product),
            "Spannung": attrs.get("Voltage", ""),
            "Zertifizierung": attrs.get("Certification", ""),
            "Information": information,
            "Datenblatt": product.datasheet_url or "",
            "Montageanleitung": montageanleitung,
            "": "",  # Trailing empty column
        }
    )

    # Update category and tag fields with conditional values
    row["Kategorienstruktur"] = kategorienstruktur
    row["Übergkategorie"] = ubergkategorie
    row["Schlagwörter"] = schlagworter

    return row
