"""Lodes.com product scraper implementation.

Following CLAUDE.md: manufacturer-specific logic only, inherits common functionality.
Based on lodes_structure.md selector mappings.
"""

import re
from typing import Optional

from loguru import logger
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.scrapers.base_scraper import BaseScraper
from src.scrapers.attribute_parser import (
    parse_designer_from_title,
    parse_table_header_attributes,
    parse_weight_from_text,
    parse_weight_to_float,
    parse_hills_from_text,
    extract_certifications_from_html,
)
from src.types import EAN, SKU, ImageUrl, Manufacturer, ProductData, ScraperConfig


class LodesScraper(BaseScraper):
    """Scraper for Lodes.com product pages."""

    MIN_DESCRIPTION_LENGTH = 20
    MAX_IMAGES = 10

    def __init__(self):
        """Initialize Lodes scraper with default configuration."""
        config = ScraperConfig(
            manufacturer=Manufacturer("lodes"),
            base_url="https://www.lodes.com",
            rate_limit_delay=1.0,  # ≤1 req/sec per lodes_structure.md
            max_retries=3,
            timeout=30,
            language_priority=["de", "en"],  # Try German first, fall back to English
            default_price=0.0,
        )
        super().__init__(config)

    def build_product_url(self, sku: SKU, language: str = "en") -> str:
        """Construct product URL from SKU with language support.

        Args:
            sku: Product identifier/slug
            language: Language code (e.g., "de", "en")

        Returns:
            Full product URL
        """
        return f"{self.config.base_url}/{language}/products/{sku}/"

    def _ensure_browser(self) -> None:
        """Ensure browser is initialized and ready for use."""
        if self._page is None:
            self.setup_browser()
        assert self._page is not None

    def scrape_category(self, category_url: str) -> list[SKU]:
        """Discover all product SKUs from a Lodes category page.

        Args:
            category_url: URL of category/collection page

        Returns:
            List of discovered product SKUs

        Raises:
            Exception: If category scraping fails
        """
        self._ensure_browser()
        logger.info(f"Scraping Lodes category: {category_url}")

        try:
            response = self._page.goto(
                category_url,
                wait_until="networkidle",
                timeout=self.config.timeout * 1000,
            )

            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status} error for {category_url}")

            self._page.wait_for_selector("a[href*='/products/']", timeout=10000)

            for _ in range(5):
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self._page.wait_for_timeout(1000)

            product_links = self._page.query_selector_all("a[href*='/products/']")
            seen_skus = set()

            for link in product_links:
                href = link.get_attribute("href")
                if href:
                    sku = self._extract_sku_from_url(href)
                    if sku:
                        seen_skus.add(sku)

            skus = list(seen_skus)
            logger.info(f"Found {len(skus)} products in category {category_url}")
            self.rate_limit()

            return skus

        except Exception as e:
            logger.error(f"Failed to scrape category {category_url}: {e}")
            raise

    def _extract_sku_from_url(self, url: str) -> SKU | None:
        """Extract product SKU/slug from product URL.

        Args:
            url: Product URL (e.g., /en/products/kelly/ or https://www.lodes.com/en/products/kelly/)

        Returns:
            Product SKU/slug or None if not found
        """
        # Match /products/{slug}/ pattern
        match = re.search(r"/products/([^/]+)", url)
        if match:
            return SKU(match.group(1))
        return None

    def scrape_product(self, sku: SKU) -> ProductData:
        """Extract product data from Lodes product page with multi-language support.

        Args:
            sku: Product SKU/name slug

        Returns:
            Structured product data

        Raises:
            ValueError: If SKU is invalid
            Exception: If scraping fails or page not found in all languages
        """
        # Validate SKU
        if not sku or not sku.strip():
            raise ValueError("SKU cannot be empty")

        if not re.match(r"^[a-zA-Z0-9_-]+$", sku):
            raise ValueError(f"SKU contains invalid characters: {sku}")

        self._ensure_browser()

        # Try languages in priority order
        languages = self.config.language_priority or ["en"]
        last_error = None
        scraped_lang = None
        url = None

        for lang in languages:
            url = self.build_product_url(sku, language=lang)
            logger.info(f"Trying to scrape Lodes product ({lang}): {url}")

            try:
                response = self._page.goto(
                    url, wait_until="networkidle", timeout=self.config.timeout * 1000
                )

                if response and response.status >= 400:
                    logger.warning(
                        f"HTTP {response.status} for {url}, trying next language"
                    )
                    last_error = Exception(f"HTTP {response.status} error for {url}")
                    continue

                # Successfully loaded page
                scraped_lang = lang
                logger.info(f"Successfully loaded page in {lang}")
                break

            except Exception as e:
                logger.warning(f"Failed to load {url}: {e}, trying next language")
                last_error = e
                continue

        # Verify we successfully loaded a page
        if scraped_lang is None:
            logger.error(f"Failed to load product {sku} in any language")
            raise last_error if last_error else Exception(f"Could not scrape {sku}")

        try:
            name = self._extract_product_name(self._page)
            description = self._extract_description(self._page)
            images = self._extract_images(self._page)
            attributes = self._extract_attributes(self._page)
            categories = self._extract_categories(self._page)
            variants = self._extract_variants(self._page)

            # Extract weight as float from attributes
            weight_kg = None
            if "Net weight" in attributes:
                weight_kg = parse_weight_to_float(attributes["Net weight"])

            if not variants:
                product = ProductData(
                    sku=sku,
                    name=name,
                    description=description,
                    manufacturer=self.config.manufacturer,
                    categories=categories,
                    attributes=attributes,
                    images=images,
                    weight=weight_kg,
                    scraped_language=scraped_lang,
                )

                logger.info(
                    f"Successfully scraped {name} (SKU: {sku}) in {scraped_lang}"
                )
                self.rate_limit()

                return product

            logger.info(
                f"Product {name} has {len(variants)} variants (returning simple product)"
            )

            variant_summary = f"{len(variants)} variants available"
            attributes["Variants"] = variant_summary

            product = ProductData(
                sku=sku,
                name=name,
                description=description,
                manufacturer=self.config.manufacturer,
                categories=categories,
                attributes=attributes,
                images=images,
                weight=weight_kg,
                scraped_language=scraped_lang,
            )

            logger.info(f"Successfully scraped {name} (SKU: {sku}) in {scraped_lang}")
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
        unique_images = list(dict.fromkeys(images))

        if not unique_images:
            logger.warning("No product images found")

        return unique_images[: self.MAX_IMAGES]

    def _extract_attributes(self, page: Page) -> dict[str, str]:
        """Extract technical specifications from variant dropdowns."""
        attributes = {}

        title_elem = page.query_selector("h1.inline.title-n.font26.serif")
        if title_elem:
            title_text = title_elem.text_content()
            if title_text:
                designer = parse_designer_from_title(title_text)
                if designer:
                    attributes["Designer"] = designer

        self._expand_technical_sheet_dropdown(page)

        header_texts = self._get_table_header_texts(page)
        table_attrs = parse_table_header_attributes(header_texts)
        attributes.update(table_attrs)

        # Check div.left.pesi for weight (German: Nettogewicht, English: Net weight)
        weight_elem = page.query_selector("div.left.pesi")
        if weight_elem:
            weight_text = weight_elem.text_content()
            if weight_text:
                weight = parse_weight_from_text(weight_text)
                if weight:
                    attributes["Net weight"] = weight

        # Also check secondary-info as fallback
        secondary_info = page.query_selector("div.secondary-info")
        if secondary_info:
            info_text = secondary_info.text_content()
            if info_text:
                # Try weight if not already found
                if "Net weight" not in attributes:
                    weight = parse_weight_from_text(info_text)
                    if weight:
                        attributes["Net weight"] = weight

                hills = parse_hills_from_text(info_text)
                if hills:
                    attributes["Hills"] = hills

        page_html = page.content()
        certifications = extract_certifications_from_html(page_html)
        for key, value in certifications.items():
            if key not in attributes:
                attributes[key] = value

        pdf_link = page.query_selector('a[href$=".pdf"]')
        if pdf_link:
            href = pdf_link.get_attribute("href")
            if href:
                attributes["Datasheet URL"] = href

        return attributes

    def _expand_technical_sheet_dropdown(self, page: Page) -> None:
        """Click dropdown to reveal technical specifications."""
        try:
            expand_headers = page.query_selector_all("div.header-variante")
            if expand_headers and len(expand_headers) > 0:
                expand_headers[0].click()
                page.wait_for_selector(
                    "table.table-variante", state="visible", timeout=5000
                )
        except PlaywrightTimeout as e:
            logger.warning(f"Could not expand technical sheet dropdown: {e}")

    def _get_table_header_texts(self, page: Page) -> list[str]:
        """Extract all table header texts from variant tables."""
        header_texts = []
        variant_tables = page.query_selector_all("table.table-variante")

        for table in variant_tables:
            thead = table.query_selector("thead")
            if thead:
                header_cells = thead.query_selector_all("th")
                for cell in header_cells:
                    header_text = cell.text_content()
                    if header_text:
                        header_texts.append(header_text.strip())

        return header_texts

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

    def _extract_variants(self, page: Page) -> list[dict[str, str]]:
        """Extract variant information from variant tables.

        Returns:
            List of variant dictionaries with SKU and attribute values.
            Empty list if no variants found.
        """
        variants = []

        # Look for variant table rows
        variant_tables = page.query_selector_all("table.table-variante")

        for table in variant_tables:
            rows = table.query_selector_all("tbody tr")

            # Extract header to identify attribute columns
            headers = []
            header_row = table.query_selector("thead tr")
            if header_row:
                header_cells = header_row.query_selector_all("th")
                headers = [
                    cell.text_content().strip()
                    for cell in header_cells
                    if cell.text_content()
                ]

            for row in rows:
                cells = row.query_selector_all("td")
                if not cells:
                    continue

                variant_data = {}

                # Map each cell to its corresponding header by index
                for idx, cell in enumerate(cells):
                    if idx < len(headers):
                        attr_name = headers[idx]
                        attr_value = cell.text_content()
                        if attr_value:
                            variant_data[attr_name] = attr_value.strip()

                if variant_data:
                    variants.append(variant_data)

        # Also check div.variante sections for variant names
        variant_sections = page.query_selector_all("div.variante")
        for section in variant_sections:
            header = section.query_selector(
                "div.header-variante.relative div.left.col25.font26.serif"
            )
            if header:
                name_text = header.text_content()
                if name_text and variants:
                    # Add variant type to first variant if not already present
                    variants[0]["Variant Type"] = name_text.strip()

        return variants

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
