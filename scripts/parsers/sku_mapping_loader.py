"""Shared utility for loading SKU mapping files."""

import json
import os
import re

from loguru import logger


def load_sku_mapping(
    mapping_filename: str, sku_pattern: str, manufacturer: str
) -> dict[str, dict[str, str]]:
    r"""Load SKU to product name mapping from JSON file.

    Args:
        mapping_filename: Name of the mapping JSON file (e.g., 'lodes_sku_mapping_auto.json')
        sku_pattern: Regex pattern to validate SKU format (e.g., r'^\d{4,5}$')
        manufacturer: Manufacturer name for logging (e.g., 'Lodes', 'Vibia')

    Returns:
        Dictionary mapping SKU to {product_name, url_slug}

    Raises:
        ValueError: If mapping file is invalid
    """
    mapping_file = os.path.join(os.path.dirname(__file__), mapping_filename)

    if not os.path.exists(mapping_file):
        logger.warning(f"SKU mapping file not found: {mapping_file}")
        return {}

    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        # Validate mapping structure
        if not isinstance(mapping, dict):
            raise ValueError("Mapping must be a dictionary")

        for sku, info in mapping.items():
            # Validate SKU format
            if not isinstance(sku, str) or not re.match(sku_pattern, sku):
                raise ValueError(f"Invalid {manufacturer} SKU format: {sku}")

            # Validate info structure
            if not isinstance(info, dict):
                raise ValueError(f"Invalid info for SKU {sku}: must be a dict")

            if "product_name" not in info or "url_slug" not in info:
                raise ValueError(
                    f"Invalid info for SKU {sku}: missing product_name or url_slug"
                )

            if not isinstance(info["product_name"], str):
                raise ValueError(f"Invalid product_name for SKU {sku}: must be string")

            if not isinstance(info["url_slug"], str):
                raise ValueError(f"Invalid url_slug for SKU {sku}: must be string")

        logger.info(
            f"Loaded {len(mapping)} {manufacturer} SKU mappings from {mapping_file}"
        )
        return mapping

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in mapping file {mapping_file}: {e}")
    except Exception as e:
        raise ValueError(f"Error loading mapping file {mapping_file}: {e}")
