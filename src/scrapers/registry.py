"""Manufacturer scraper registry.

Provides centralized mapping of manufacturer names to scraper classes.
Adding a new manufacturer only requires adding an entry to SCRAPER_REGISTRY.
"""

from typing import Type

from src.scrapers.base_scraper import BaseScraper
from src.scrapers.lodes_scraper import LodesScraper
from src.scrapers.vibia_scraper import VibiaScraper

# Registry of available scrapers
SCRAPER_REGISTRY: dict[str, Type[BaseScraper]] = {
    "lodes": LodesScraper,
    "vibia": VibiaScraper,
    # Future manufacturers added here:
    # "flos": FlosScraper,
}


def get_scraper_class(manufacturer: str) -> Type[BaseScraper]:
    """Get scraper class for a manufacturer.

    Args:
        manufacturer: Manufacturer name (e.g., 'lodes')

    Returns:
        Scraper class for the manufacturer

    Raises:
        ValueError: If manufacturer is not supported
    """
    if manufacturer not in SCRAPER_REGISTRY:
        available = ", ".join(SCRAPER_REGISTRY.keys())
        raise ValueError(
            f"Unknown manufacturer: {manufacturer}. Available: {available}"
        )

    return SCRAPER_REGISTRY[manufacturer]


def get_available_manufacturers() -> list[str]:
    """Get list of supported manufacturer names.

    Returns:
        List of manufacturer identifiers
    """
    return list(SCRAPER_REGISTRY.keys())
