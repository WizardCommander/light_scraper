"""Abstract base class for manufacturer-specific scrapers.

Following CLAUDE.md: shared logic in base class, specific implementation in subclasses.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional

from playwright.sync_api import sync_playwright, Browser, Page, Playwright
from loguru import logger

from src.models import SKU, ProductData, ScraperConfig
from src.downloaders.asset_downloader import download_image


class BaseScraper(ABC):
    """Abstract base class providing common scraping functionality.

    Subclasses must implement:
    - scrape_product(sku) - Extract product data from manufacturer site
    - build_product_url(sku) - Construct product URL from SKU
    """

    def __init__(self, config: ScraperConfig):
        """Initialize scraper with configuration.

        Args:
            config: Scraper configuration including rate limits, timeouts
        """
        self.config = config
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    def setup_browser(self, headless: bool = True) -> Page:
        """Initialize Playwright browser and return page instance.

        Args:
            headless: Whether to run browser in headless mode

        Returns:
            Playwright Page instance
        """
        if self._page is not None:
            return self._page

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._page = self._browser.new_page()

        logger.info(f"Browser initialized for {self.config.manufacturer}")
        return self._page

    def teardown_browser(self) -> None:
        """Close browser and cleanup resources."""
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

        self._page = None
        self._browser = None
        self._playwright = None

        logger.info(f"Browser closed for {self.config.manufacturer}")

    def rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        time.sleep(self.config.rate_limit_delay)

    def download_product_images(
        self, product: ProductData, output_dir: str = "output/images"
    ) -> list[str]:
        """Download all images for a product.

        Args:
            product: Product data containing image URLs
            output_dir: Base output directory

        Returns:
            List of local file paths for downloaded images
        """
        downloaded_paths = []

        for idx, image_url in enumerate(product.images):
            try:
                path = download_image(
                    image_url, product.sku, product.manufacturer, output_dir, idx
                )
                downloaded_paths.append(str(path))
            except Exception as e:
                logger.error(
                    f"Failed to download image {image_url} for {product.sku}: {e}"
                )

        return downloaded_paths

    @abstractmethod
    def scrape_product(self, sku: SKU) -> list[ProductData]:
        """Extract product data from manufacturer website.

        Must be implemented by each manufacturer scraper.

        Args:
            sku: Product SKU to scrape

        Returns:
            List of product data (single product or parent + variations)
            - For simple products: returns list with 1 ProductData
            - For variable products: returns list with parent + child variations

        Raises:
            Exception: If scraping fails
        """
        pass

    @abstractmethod
    def build_product_url(self, sku: SKU) -> str:
        """Construct product URL from SKU.

        Must be implemented by each manufacturer scraper.

        Args:
            sku: Product SKU

        Returns:
            Full product URL
        """
        pass

    @abstractmethod
    def scrape_category(self, category_url: str) -> list[SKU]:
        """Discover all product SKUs from a category page.

        Must be implemented by each manufacturer scraper.

        Args:
            category_url: URL of category/collection page

        Returns:
            List of discovered product SKUs

        Raises:
            Exception: If category scraping fails
        """
        pass

    def __enter__(self):
        """Context manager entry - setup browser."""
        self.setup_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - teardown browser."""
        self.teardown_browser()
