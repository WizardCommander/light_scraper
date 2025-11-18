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
    clean_variant_header_name,
    extract_certifications_from_html,
    parse_designer_from_title,
    parse_hills_from_text,
    parse_table_header_attributes,
    parse_weight_from_text,
    parse_weight_to_float,
)
from src.types import EAN, SKU, ImageUrl, Manufacturer, ProductData, ScraperConfig


class LodesScraper(BaseScraper):
    """Scraper for Lodes.com product pages."""

    # Configuration constants
    MIN_DESCRIPTION_LENGTH = 20
    MAX_IMAGES = 10
    IMAGE_EXCLUDE_PATTERNS = [
        "logo",
        "icon",
        "banner",
        "cookie",
        ".svg",
        "avatar",
        "placeholder",
    ]

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

    def _convert_to_german_url(self, url: str) -> str:
        """Convert any Lodes URL to German version."""
        if "/de/" in url:
            return url
        url = url.replace("https://www.lodes.com/", "https://www.lodes.com/de/")
        url = url.replace("https://www.lodes.com/en/", "https://www.lodes.com/de/")
        url = url.replace("https://www.lodes.com/fr/", "https://www.lodes.com/de/")
        return url

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
        category_url = self._convert_to_german_url(category_url)
        logger.info(f"Scraping Lodes category (German): {category_url}")

        try:
            response = self._page.goto(
                category_url,
                wait_until="networkidle",
                timeout=self.config.timeout * 1000,
            )

            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status} error for {category_url}")

            # Scroll to load all products
            for _ in range(5):
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self._page.wait_for_timeout(1000)

            # Debug: log all links to understand page structure
            all_links = self._page.query_selector_all("a[href]")
            logger.debug(f"Found {len(all_links)} total links on page")
            sample_hrefs = [link.get_attribute("href") for link in all_links[:20]]
            logger.debug(f"Sample links: {sample_hrefs}")

            # Try various product link patterns (producten, prodotti, produkte, products)
            product_links = self._page.query_selector_all(
                "a[href*='/producten/'], a[href*='/prodotti/'], a[href*='/produkte/'], a[href*='/products/']"
            )
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
            url: Product URL (e.g., /en/producten/kelly/ or https://www.lodes.com/de/producten/kelly/)

        Returns:
            Product SKU/slug or None if not found
        """
        # Match various product URL patterns (producten, products, prodotti, produkte)
        match = re.search(r"/(?:producten|products|prodotti|produkte)/([^/?]+)", url)
        if match:
            return SKU(match.group(1))
        return None

    def scrape_product(self, sku: SKU) -> list[ProductData]:
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
                # Validate weight is positive
                if weight_kg is not None and weight_kg <= 0:
                    logger.warning(
                        f"Invalid weight value {weight_kg} kg, setting to None"
                    )
                    weight_kg = None

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

                return [product]

            # Product has variants - create variable product with children
            logger.info(
                f"Product {name} has {len(variants)} variants (creating variable product)"
            )

            products = self._build_variable_products(
                parent_sku=sku,
                name=name,
                description=description,
                categories=categories,
                attributes=attributes,
                images=images,
                variants=variants,
                weight_kg=weight_kg,
                scraped_lang=scraped_lang,
            )

            logger.info(
                f"Successfully scraped {name} with {len(products)-1} variations"
            )
            self.rate_limit()

            return products

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

                # Validate URL format
                if self._is_valid_url(full_src):
                    images.append(ImageUrl(full_src))
                else:
                    logger.warning(f"Invalid image URL skipped: {full_src}")

        # Remove duplicates while preserving order
        unique_images = list(dict.fromkeys(images))

        if not unique_images:
            logger.warning("No product images found")

        return unique_images[: self.MAX_IMAGES]

    def _extract_attributes(self, page: Page) -> dict[str, str]:
        """Extract technical specifications from variant dropdowns."""
        attributes = {}

        attributes.update(self._extract_designer(page))
        attributes.update(self._extract_table_attributes(page))
        attributes.update(self._extract_weight_from_pesi(page))
        attributes.update(self._extract_from_secondary_info(page, attributes))
        attributes.update(self._extract_certifications(page, attributes))
        attributes.update(self._extract_pdf_link(page))

        return attributes

    def _extract_designer(self, page: Page) -> dict[str, str]:
        """Extract designer from product title."""
        try:
            title_elem = page.query_selector("h1.inline.title-n.font26.serif")
            if title_elem:
                title_text = title_elem.text_content()
                if title_text:
                    designer = parse_designer_from_title(title_text)
                    if designer:
                        return {"Designer": designer}
        except Exception as e:
            logger.warning(f"Failed to extract designer: {e}")
        return {}

    def _extract_table_attributes(self, page: Page) -> dict[str, str]:
        """Extract attributes from technical specification table."""
        try:
            self._expand_technical_sheet_dropdown(page)
            header_texts = self._get_table_header_texts(page)
            return parse_table_header_attributes(header_texts)
        except Exception as e:
            logger.warning(f"Failed to extract table attributes: {e}")
            return {}

    def _extract_weight_from_pesi(self, page: Page) -> dict[str, str]:
        """Extract weight from div.left.pesi element."""
        try:
            weight_elem = page.query_selector("div.left.pesi")
            if weight_elem:
                weight_text = weight_elem.text_content()
                if weight_text:
                    weight = parse_weight_from_text(weight_text)
                    if weight:
                        return {"Net weight": weight}
        except Exception as e:
            logger.warning(f"Failed to extract weight from pesi div: {e}")
        return {}

    def _extract_from_secondary_info(
        self, page: Page, existing_attrs: dict[str, str]
    ) -> dict[str, str]:
        """Extract weight and hills from secondary-info as fallback."""
        try:
            secondary_info = page.query_selector("div.secondary-info")
            if secondary_info:
                info_text = secondary_info.text_content()
                if info_text:
                    extracted = {}

                    # Try weight if not already found
                    if "Net weight" not in existing_attrs:
                        weight = parse_weight_from_text(info_text)
                        if weight:
                            extracted["Net weight"] = weight

                    hills = parse_hills_from_text(info_text)
                    if hills:
                        extracted["Hills"] = hills

                    return extracted
        except Exception as e:
            logger.warning(f"Failed to extract from secondary-info: {e}")
        return {}

    def _extract_certifications(
        self, page: Page, existing_attrs: dict[str, str]
    ) -> dict[str, str]:
        """Extract certifications from page HTML."""
        try:
            page_html = page.content()
            certifications = extract_certifications_from_html(page_html)
            # Only add certifications not already present
            return {
                key: value
                for key, value in certifications.items()
                if key not in existing_attrs
            }
        except Exception as e:
            logger.warning(f"Failed to extract certifications: {e}")
            return {}

    def _extract_pdf_link(self, page: Page) -> dict[str, str]:
        """Extract PDF datasheet link."""
        try:
            # Try specific selector first, fallback to generic
            pdf_link = page.query_selector("a.pdf-link") or page.query_selector(
                'a[href$=".pdf"]'
            )
            if pdf_link:
                href = pdf_link.get_attribute("href")
                if href:
                    return {"Datasheet URL": href}
        except Exception as e:
            logger.warning(f"Failed to extract PDF link: {e}")
        return {}

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
                if text and text.strip():
                    category = text.strip()
                    # Validate category is meaningful (not just whitespace/special chars)
                    if len(category) > 0 and not category.isspace():
                        categories.append(category)

            bred3_link = breadcrumb_container.query_selector("span.bred3 a")
            if bred3_link:
                text = bred3_link.text_content()
                if text and text.strip():
                    category = text.strip()
                    if len(category) > 0 and not category.isspace():
                        categories.append(category)

        # Filter out any empty strings that may have slipped through
        categories = [c for c in categories if c and c.strip()]

        return categories if categories else ["Lighting"]

    @staticmethod
    def _extract_variation_attribute_names(variants: list[dict[str, str]]) -> set[str]:
        """Extract attribute names that vary across product variants.

        Args:
            variants: List of variant dictionaries

        Returns:
            Set of attribute names (excluding "Code")
        """
        variation_attr_names = set()
        for variant in variants:
            variation_attr_names.update(variant.keys())

        variation_attr_names.discard("Code")
        return variation_attr_names

    @staticmethod
    def _build_parent_variation_attributes(
        variants: list[dict[str, str]], variation_attr_names: set[str]
    ) -> dict[str, str]:
        """Build parent product variation attributes with ALL possible values.

        Args:
            variants: List of variant dictionaries
            variation_attr_names: Set of variation attribute names

        Returns:
            Dict mapping attribute names to comma-separated lists of all values
        """
        parent_variation_attrs = {}

        for attr_name in variation_attr_names:
            values = set()
            for variant in variants:
                if attr_name in variant and variant[attr_name]:
                    values.add(variant[attr_name])

            if values:
                parent_variation_attrs[attr_name] = ", ".join(sorted(values))

        return parent_variation_attrs

    @staticmethod
    def _build_variation_name(
        base_name: str,
        variant: dict[str, str],
        variation_attr_names: set[str],
        idx: int,
    ) -> str:
        """Build descriptive name for a product variation.

        Args:
            base_name: Parent product name
            variant: Variant data dict
            variation_attr_names: Set of variation attribute names
            idx: Variant index (for fallback naming)

        Returns:
            Formatted variation name
        """
        variant_details = []
        for attr_name in sorted(variation_attr_names):
            if attr_name in variant and variant[attr_name]:
                variant_details.append(variant[attr_name])

        if variant_details:
            return f"{base_name} - {' / '.join(variant_details)}"
        return f"{base_name} - Variant {idx+1}"

    def _build_variable_products(
        self,
        parent_sku: SKU,
        name: str,
        description: str,
        categories: list[str],
        attributes: dict[str, str],
        images: list[ImageUrl],
        variants: list[dict[str, str]],
        weight_kg: float | None,
        scraped_lang: str,
    ) -> list[ProductData]:
        """Build parent + child variation products from variant data.

        Args:
            parent_sku: SKU for parent product (used as reference for children)
            name: Product name
            description: Product description
            categories: Product categories
            attributes: Product attributes (Designer, IP Rating, etc.)
            images: Product images
            variants: List of variant dicts with Code, Structure, Diffusor, etc.
            weight_kg: Product weight in kg
            scraped_lang: Language code

        Returns:
            List with 1 parent + N child variation ProductData objects
        """
        if not variants:
            return []

        variation_attr_names = self._extract_variation_attribute_names(variants)
        parent_variation_attrs = self._build_parent_variation_attributes(
            variants, variation_attr_names
        )

        parent = ProductData(
            sku=SKU(""),
            name=name,
            description=description,
            manufacturer=self.config.manufacturer,
            categories=categories,
            attributes=attributes,
            images=images,
            product_type="variable",
            weight=weight_kg,
            scraped_language=scraped_lang,
            variation_attributes=parent_variation_attrs,
        )

        children = []
        for idx, variant in enumerate(variants):
            variant_sku = variant.get("Code", f"{parent_sku}-{idx+1}")
            variant_name = self._build_variation_name(
                name, variant, variation_attr_names, idx
            )

            child_variation_attrs = {
                attr_name: variant[attr_name]
                for attr_name in variation_attr_names
                if attr_name in variant and variant[attr_name]
            }

            child = ProductData(
                sku=SKU(variant_sku),
                name=variant_name,
                description="",
                manufacturer=self.config.manufacturer,
                categories=[],
                attributes={},
                images=[],
                product_type="variation",
                parent_sku=parent_sku,
                variation_attributes=child_variation_attrs,
                weight=weight_kg,
                scraped_language=scraped_lang,
            )
            children.append(child)

        return [parent] + children

    def _extract_variants(self, page: Page) -> list[dict[str, str]]:
        """Extract variant information from variant tables.

        Returns:
            List of variant dictionaries with SKU and attribute values.
            Empty list if no variants found.
        """
        variants = []

        variant_tables = page.query_selector_all("table.table-variante")

        for table in variant_tables:
            header_map = self._build_header_index_map(table)
            rows = table.query_selector_all("tbody tr")

            for row in rows:
                variant_data = self._parse_variant_row(row, header_map)
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

    def _build_header_index_map(self, table) -> list[tuple[int, str]]:
        """Build mapping of cell indices to cleaned header names.

        Note: First column is often a variant group identifier (e.g., "Kelly medium dome 60")
        so we keep it even if it looks like a variant name.

        Args:
            table: Table element containing thead with header cells

        Returns:
            List of (index, cleaned_header_name) tuples
        """
        header_map = []
        header_row = table.query_selector("thead tr")

        if header_row:
            header_cells = header_row.query_selector_all("th")
            for idx, cell in enumerate(header_cells):
                if cell.text_content():
                    cleaned = clean_variant_header_name(cell.text_content())
                    # Keep first column even if filtering would remove it (it's a grouping header)
                    if cleaned or idx == 0:
                        final_name = cleaned if cleaned else cell.text_content().strip()
                        header_map.append((idx, final_name))

        return header_map

    def _parse_variant_row(
        self, row, header_map: list[tuple[int, str]]
    ) -> dict[str, str]:
        """Parse a variant table row into attribute dictionary.

        Args:
            row: Table row element containing td cells
            header_map: List of (cell_index, attribute_name) tuples

        Returns:
            Dictionary of attribute names to values, or empty dict if no data
        """
        cells = row.query_selector_all("td")
        if not cells:
            return {}

        variant_data = {}

        # Map cells to headers using the index mapping
        for cell_idx, attr_name in header_map:
            if cell_idx < len(cells):
                attr_value = cells[cell_idx].text_content()
                if attr_value:
                    variant_data[attr_name] = attr_value.strip()

        return variant_data

    def _is_product_image(self, src: str) -> bool:
        """Filter out non-product images (logos, icons, etc.)."""
        src_lower = src.lower()
        return not any(pattern in src_lower for pattern in self.IMAGE_EXCLUDE_PATTERNS)

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format.

        Args:
            url: URL string to validate

        Returns:
            True if URL is valid, False otherwise
        """
        if not url:
            return False

        # Check if URL starts with http:// or https:// or //
        url_normalized = url.strip().lower()
        if not url_normalized:
            return False

        if not (
            url_normalized.startswith("http://")
            or url_normalized.startswith("https://")
            or url_normalized.startswith("//")
        ):
            return False

        return True

    def _get_full_resolution_url(self, src: str) -> str:
        """Convert thumbnail or scaled URLs to full resolution."""
        # Remove common size suffixes
        full_url = src.replace("-scaled", "")
        full_url = full_url.replace("-150x150", "")
        full_url = full_url.replace("-300x300", "")
        full_url = full_url.replace("-1024x1024", "")

        return full_url
