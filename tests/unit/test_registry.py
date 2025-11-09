"""Unit tests for manufacturer scraper registry.

Following CLAUDE.md: test registry functions thoroughly.
"""

import pytest

from src.scrapers.registry import (
    get_scraper_class,
    get_available_manufacturers,
    SCRAPER_REGISTRY,
)
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.lodes_scraper import LodesScraper


@pytest.mark.unit
def test_get_scraper_class_returns_correct_class():
    """Should return correct scraper class for manufacturer."""
    scraper_class = get_scraper_class("lodes")

    assert scraper_class == LodesScraper
    assert issubclass(scraper_class, BaseScraper)


@pytest.mark.unit
def test_get_scraper_class_unknown_manufacturer_raises():
    """Should raise ValueError for unknown manufacturer."""
    with pytest.raises(ValueError, match="Unknown manufacturer"):
        get_scraper_class("unknown-manufacturer")


@pytest.mark.unit
def test_get_scraper_class_error_message_shows_available():
    """Should show available manufacturers in error message."""
    try:
        get_scraper_class("invalid")
    except ValueError as e:
        assert "lodes" in str(e).lower()


@pytest.mark.unit
def test_get_available_manufacturers_returns_list():
    """Should return list of available manufacturer names."""
    manufacturers = get_available_manufacturers()

    assert isinstance(manufacturers, list)
    assert len(manufacturers) > 0
    assert "lodes" in manufacturers


@pytest.mark.unit
def test_registry_contains_valid_scrapers():
    """Should verify all scrapers in registry are valid."""
    for name, scraper_class in SCRAPER_REGISTRY.items():
        # Name should be lowercase string
        assert isinstance(name, str)
        assert name == name.lower()

        # Class should be subclass of BaseScraper
        assert issubclass(scraper_class, BaseScraper)


@pytest.mark.unit
def test_scraper_can_be_instantiated():
    """Should be able to instantiate scrapers from registry."""
    scraper_class = get_scraper_class("lodes")
    scraper = scraper_class()

    assert isinstance(scraper, BaseScraper)
    assert isinstance(scraper, LodesScraper)
