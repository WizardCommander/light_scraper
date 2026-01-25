"""Abstract base class for manufacturer-specific scrapers.

Following CLAUDE.md: shared logic in base class, specific implementation in subclasses.
"""

import glob
import os
import platform
import subprocess
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

        # On Mac, Playwright needs explicit executable path within Chromium.app bundle
        launch_options = {"headless": headless}
        if os.getenv("PLAYWRIGHT_BROWSERS_PATH") and os.name != "nt":
            # Mac/Linux: Chromium is packaged as .app bundle
            if platform.system() == "Darwin":
                browsers_path = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
                logger.debug(f"PLAYWRIGHT_BROWSERS_PATH: {browsers_path}")

                # Find the chromium directory
                chromium_dirs = glob.glob(f"{browsers_path}/chromium-*")
                if chromium_dirs:
                    chromium_dir = chromium_dirs[0]
                    # Check for ARM Mac (chrome-mac-arm64) or Intel Mac (chrome-mac)
                    chrome_mac_dirs = glob.glob(f"{chromium_dir}/chrome-mac*")
                    if chrome_mac_dirs:
                        chrome_mac_dir = chrome_mac_dirs[0]
                        # Try different browser app names (Playwright changed from Chromium to Chrome for Testing)
                        possible_paths = [
                            f"{chrome_mac_dir}/Chromium.app/Contents/MacOS/Chromium",
                            f"{chrome_mac_dir}/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
                        ]
                        executable_path = None
                        for path in possible_paths:
                            if os.path.exists(path):
                                executable_path = path
                                break
                    else:
                        executable_path = None
                    if executable_path and os.path.exists(executable_path):
                        launch_options["executable_path"] = executable_path
                        logger.debug(
                            f"Using Mac Chromium executable: {executable_path}"
                        )
                    else:
                        # Mac browser not found - try runtime fallback
                        logger.warning(
                            f"Mac Chromium not found at: {executable_path}. "
                            f"Contents of {chromium_dir}: {os.listdir(chromium_dir)}"
                        )
                        fallback_path = self._ensure_mac_browser_installed(
                            browsers_path
                        )
                        if fallback_path:
                            launch_options["executable_path"] = fallback_path
                        else:
                            logger.error(
                                "Could not find or download Mac Chromium browser. "
                                "The app bundle may be corrupted. Please reinstall."
                            )
                else:
                    logger.warning(f"No chromium directory found in: {browsers_path}")
                    # Try to download browser as fallback
                    fallback_path = self._ensure_mac_browser_installed(browsers_path)
                    if fallback_path:
                        launch_options["executable_path"] = fallback_path

        self._browser = self._playwright.chromium.launch(**launch_options)
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

    def _ensure_mac_browser_installed(self, browsers_path: str) -> Optional[str]:
        """Attempt to install Mac Chromium if missing.

        Args:
            browsers_path: Path to Playwright browsers directory

        Returns:
            Path to Chromium executable if successful, None otherwise
        """
        logger.warning("Bundled Mac browser not found. Attempting to download...")
        try:
            env = os.environ.copy()
            env["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path
            result = subprocess.run(
                ["playwright", "install", "chromium"],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            logger.debug(f"Playwright install output: {result.stdout}")

            # Re-check for browser after install
            chromium_dirs = glob.glob(f"{browsers_path}/chromium-*")
            if chromium_dirs:
                # Check for ARM Mac (chrome-mac-arm64) or Intel Mac (chrome-mac)
                chrome_mac_dirs = glob.glob(f"{chromium_dirs[0]}/chrome-mac*")
                if chrome_mac_dirs:
                    chrome_mac_dir = chrome_mac_dirs[0]
                    # Try different browser app names
                    possible_paths = [
                        f"{chrome_mac_dir}/Chromium.app/Contents/MacOS/Chromium",
                        f"{chrome_mac_dir}/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
                    ]
                    for path in possible_paths:
                        if os.path.exists(path):
                            logger.info(
                                f"Successfully downloaded Mac browser to: {path}"
                            )
                            return path
                    logger.error(
                        f"Downloaded but executable not found. Checked: {possible_paths}"
                    )
                else:
                    logger.error(
                        f"No chrome-mac directory found in: {chromium_dirs[0]}"
                    )
            else:
                logger.error(f"No chromium directory created in: {browsers_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to download Chromium: {e.stderr}")
        except FileNotFoundError:
            logger.error(
                "Playwright CLI not found. Cannot download browser. "
                "Please install playwright: pip install playwright"
            )
        except Exception as e:
            logger.error(f"Unexpected error downloading Chromium: {e}")
        return None

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
    def scrape_product(
        self, sku: SKU, output_base: str = "output"
    ) -> list[ProductData]:
        """Extract product data from manufacturer website.

        Must be implemented by each manufacturer scraper.

        Args:
            sku: Product SKU to scrape
            output_base: Base output directory for downloaded files (default: "output")

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
