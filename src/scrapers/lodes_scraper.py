"""Lodes.com product scraper implementation.

Following CLAUDE.md: manufacturer-specific logic only, inherits common functionality.
Based on lodes_structure.md selector mappings.
"""

from typing import Optional
from playwright.sync_api import Page
from loguru import logger

from src.scrapers.base_scraper import BaseScraper
from src.types import SKU, ProductData, ScraperConfig, ImageUrl, Manufacturer, EAN


class LodesScraper(BaseScraper):
    """Scraper for Lodes.com product pages."""

    MIN_DESCRIPTION_LENGTH = 20
    MAX_IMAGES = 10

    def __init__(self):
        """Initialize Lodes scraper with default configuration."""
        config = ScraperConfig(
            manufacturer=Manufacturer("lodes"),
            base_url="https://www.lodes.com/en",
            rate_limit_delay=1.0,  # ≤1 req/sec per lodes_structure.md
            max_retries=3,
            timeout=30,
        )
        super().__init__(config)

    def build_product_url(self, sku: SKU) -> str:
        """Construct product URL from SKU.

        Note: Lodes uses product name slugs in URLs, not numeric SKUs.
        This method assumes SKU is the product slug (e.g., 'a-tube-suspension').

        Args:
            sku: Product identifier/slug

        Returns:
            Full product URL
        """
        return f"{self.config.base_url}/products/{sku}/"

    def scrape_product(self, sku: SKU) -> ProductData:
        """Extract product data from Lodes product page.

        Args:
            sku: Product SKU/name slug

        Returns:
            Structured product data

        Raises:
            Exception: If scraping fails or page not found
        """
        if self._page is None:
            self.setup_browser()

        assert self._page is not None

        url = self.build_product_url(sku)
        logger.info(f"Scraping Lodes product: {url}")

        try:
            # Wait for JavaScript-loaded content
            response = self._page.goto(
                url, wait_until="networkidle", timeout=self.config.timeout * 1000
            )

            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status} error for {url}")

        except Exception as e:
            logger.error(f"Failed to load page {url}: {e}")
            raise

        # Extract product data using lodes_structure.md selectors
        try:
            name = self._extract_product_name(self._page)
            description = self._extract_description(self._page)
            images = self._extract_images(self._page)
            attributes = self._extract_attributes(self._page)
            categories = self._extract_categories(self._page)
            variants_info = self._extract_variants(self._page)

            # Combine variant info into attributes
            if variants_info:
                attributes.update(variants_info)

            product = ProductData(
                sku=sku,
                name=name,
                description=description,
                manufacturer=self.config.manufacturer,
                categories=categories,
                attributes=attributes,
                images=images,
            )

            logger.info(f"Successfully scraped {name} (SKU: {sku})")
            self.rate_limit()

            return product

        except Exception as e:
            logger.error(f"Failed to extract data from {url}: {e}")
            raise

    def _extract_product_name(self, page: Page) -> str:
        """Extract product name from h1.inline.title-n.font26.serif."""
        title_elem = page.query_selector("h1.inline.title-n.font26.serif")
        if title_elem:
            text = title_elem.text_content()
            if text:
                return text.strip()

        # Fallback to page title
        title = page.title()
        return title.split("|")[0].strip() if title else "Unknown Product"

    def _extract_description(self, page: Page) -> str:
        """Extract product description from div.largh60.pos-Sinistra."""
        # Primary selector for description
        desc_elem = page.query_selector("div.largh60.pos-Sinistra")
        if desc_elem:
            text = desc_elem.text_content()
            if text and len(text.strip()) > self.MIN_DESCRIPTION_LENGTH:
                return text.strip()

        # Alternative selector
        desc_elem = page.query_selector("div.font26.serif.text-more")
        if desc_elem:
            text = desc_elem.text_content()
            if text and len(text.strip()) > self.MIN_DESCRIPTION_LENGTH:
                return text.strip()

        logger.warning("No description found for product")
        return "No description available"

    def _extract_images(self, page: Page) -> list[ImageUrl]:
        """Extract product image URLs from carousel."""
        images = []

        # Primary selector for carousel images
        carousel_images = page.query_selector_all("img.carousel-cell-image")

        for img in carousel_images:
            src = img.get_attribute("src")
            if src and self._is_product_image(src):
                # Get full resolution URL
                full_src = self._get_full_resolution_url(src)
                images.append(ImageUrl(full_src))

        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for img in images:
            if img not in seen:
                seen.add(img)
                unique_images.append(img)

        if not unique_images:
            logger.warning("No product images found")

        return unique_images[: self.MAX_IMAGES]

    def _extract_attributes(self, page: Page) -> dict[str, str]:
        """Extract technical specifications from tables."""
        attributes = {}

        # Extract designer from h1 title
        title_elem = page.query_selector("h1.inline.title-n.font26.serif")
        if title_elem:
            em_elem = title_elem.query_selector("em")
            if em_elem:
                designer_text = em_elem.text_content()
                if designer_text and "Design by" in designer_text:
                    designer_name = designer_text.replace("Design by", "").strip()
                    if designer_name:
                        attributes["Designer"] = designer_name

        # Extract technical specs from variant tables
        variant_tables = page.query_selector_all("table.table-variante")
        for table in variant_tables:
            rows = table.query_selector_all("tbody tr")
            for row in rows:
                header = row.query_selector("th")
                cell = row.query_selector("td")
                if header and cell:
                    key_text = header.text_content()
                    value_text = cell.text_content()
                    if key_text and value_text:
                        attributes[key_text.strip()] = value_text.strip()

        # Extract datasheet PDF link
        pdf_link = page.query_selector('a[href$=".pdf"]')
        if pdf_link:
            href = pdf_link.get_attribute("href")
            if href:
                attributes["Datasheet URL"] = href

        return attributes

    def _extract_categories(self, page: Page) -> list[str]:
        """Extract product categories from breadcrumbs."""
        categories = []

        # Extract from breadcrumb navigation
        breadcrumb_container = page.query_selector("div.bread-crumbs.shadow")
        if breadcrumb_container:
            # Get links from bred2 and bred3 spans
            bred2_link = breadcrumb_container.query_selector("span.bred2 a")
            if bred2_link:
                text = bred2_link.text_content()
                if text:
                    categories.append(text.strip())

            bred3_link = breadcrumb_container.query_selector("span.bred3 a")
            if bred3_link:
                text = bred3_link.text_content()
                if text:
                    categories.append(text.strip())

        return categories if categories else ["Lighting"]

    def _extract_variants(self, page: Page) -> dict[str, str]:
        """Extract variant information from div.variante."""
        variants_data = {}
        variant_names = []

        # Look for variant sections
        variants = page.query_selector_all("div.variante")

        for variant in variants:
            # Extract variant name from header
            header = variant.query_selector(
                "div.header-variante.relative div.left.col25.font26.serif"
            )
            if header:
                name_text = header.text_content()
                if name_text:
                    variant_names.append(name_text.strip())

        if variant_names:
            variants_data["Variants"] = ", ".join(variant_names)

        return variants_data

    def _is_product_image(self, src: str) -> bool:
        """Filter out non-product images (logos, icons, etc.)."""
        exclude_patterns = [
            "logo",
            "icon",
            "banner",
            "cookie",
            ".svg",
            "avatar",
            "placeholder",
        ]
        src_lower = src.lower()
        return not any(pattern in src_lower for pattern in exclude_patterns)

    def _get_full_resolution_url(self, src: str) -> str:
        """Convert thumbnail or scaled URLs to full resolution."""
        # Remove common size suffixes
        full_url = src.replace("-scaled", "")
        full_url = full_url.replace("-150x150", "")
        full_url = full_url.replace("-300x300", "")
        full_url = full_url.replace("-1024x1024", "")

        return full_url
