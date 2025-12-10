"""Lodes.com product scraper implementation.

Following CLAUDE.md: manufacturer-specific logic only, inherits common functionality.
Based on lodes_structure.md selector mappings.
"""

import re

from loguru import logger
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.scrapers.base_scraper import BaseScraper
from src.scrapers.attribute_parser import (
    clean_variant_header_name,
    extract_certifications_from_html,
    parse_designer_from_title,
    parse_dimensions_from_text,
    parse_hills_from_text,
    parse_kelvin_from_text,
    parse_table_header_attributes,
    parse_weight_from_text,
    parse_weight_to_float,
)
from src.models import SKU, ImageUrl, Manufacturer, ProductData, ScraperConfig
from src import lodes_price_list


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

    # Product code pattern (format: "14126 1000" - 5 digits, space, 4 digits)
    PRODUCT_CODE_PATTERN = r"^\d{5}\s+\d{4}$"

    # Color name to code mapping (handles Italian/English/German names)
    COLOR_NAME_TO_CODE = {
        "bianco opaco": "1000",
        "bianco": "1000",
        "matte white": "1000",
        "white": "1000",
        "weiß matt": "1000",
        "weiß": "1000",
        "9010": "1000",
        "nero opaco": "2000",
        "nero": "2000",
        "matte black": "2000",
        "black": "2000",
        "schwarz matt": "2000",
        "schwarz": "2000",
        "9005": "2000",
        "bronzo ramato": "3500",
        "coppery bronze": "3500",
        "bronze": "3500",
        "champagne opaco": "4500",
        "matte champagne": "4500",
        "champagne": "4500",
        "champagner matt": "4500",
        "champagner": "4500",
    }

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

        Note:
            German pages use "producten", English uses "products"
        """
        product_path = "producten" if language == "de" else "products"
        return f"{self.config.base_url}/{language}/{product_path}/{sku}/"

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

        # Check if this product has price list data
        price_list_products = lodes_price_list.get_product_by_slug(sku)
        if price_list_products:
            logger.info(
                f"Found {len(price_list_products)} product(s) in price list for slug '{sku}'"
            )

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

            # Parse dimensions from attributes
            dimensions = None
            if "Dimensions" in attributes:
                dimensions = parse_dimensions_from_text(attributes["Dimensions"])
                if dimensions:
                    logger.info(f"Parsed dimensions: {dimensions}")

            # Parse Kelvin from attributes
            light_specs = None
            if "Kelvin" in attributes:
                light_specs = {"kelvin": attributes["Kelvin"]}
                logger.info(f"Parsed Kelvin: {attributes['Kelvin']}")

            # Extract installation manual URL
            installation_manual = self._extract_installation_manual_url(self._page)
            if installation_manual:
                logger.info(f"Found installation manual: {installation_manual}")

            # Extract cable length
            cable_length = self._extract_cable_length(self._page)
            if cable_length:
                logger.info(f"Found cable length: {cable_length}")

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
                    dimensions=dimensions,
                    light_specs=light_specs,
                    datasheet_url=attributes.get("Datasheet URL"),
                    installation_manual_url=installation_manual,
                    cable_length=cable_length,
                    product_notes="Leuchtmittel nicht inkludiert.",
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
                dimensions=dimensions,
                light_specs=light_specs,
                installation_manual=installation_manual,
                cable_length=cable_length,
                scraped_lang=scraped_lang,
                url_slug=sku,
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

        # Extract from secondary-info (fallback for weight, also has hills)
        secondary_attrs = self._extract_from_secondary_info(page)
        # Only use weight from secondary-info if not already found
        if "Net weight" not in attributes and "Net weight" in secondary_attrs:
            attributes["Net weight"] = secondary_attrs["Net weight"]
        # Always add hills if found
        if "Hills" in secondary_attrs:
            attributes["Hills"] = secondary_attrs["Hills"]

        attributes.update(self._extract_certifications(page, attributes))
        attributes.update(self._extract_pdf_link(page))

        # Extract dimensions and Kelvin from table cells
        attributes.update(self._extract_dimensions_and_kelvin(page))

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

    def _extract_from_secondary_info(self, page: Page) -> dict[str, str]:
        """Extract weight and hills from secondary-info element.

        Returns all found attributes. Caller decides whether to use them
        based on what's already been extracted.
        """
        try:
            secondary_info = page.query_selector("div.secondary-info")
            if secondary_info:
                info_text = secondary_info.text_content()
                if info_text:
                    extracted = {}

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
        """Extract PDF datasheet link from Spec Sheet button."""
        try:
            # Lodes has download buttons with class "bottone white-button"
            # Look for "Spec Sheet" / "Scheda prodotto" button
            selectors = [
                'a.bottone.white-button:has-text("Spec Sheet")',
                'a[data-name="Scheda prodotto"]',
                'a.bottone:has-text("Spec Sheet")',
                'a:has-text("Spec Sheet")',
                "a.pdf-link",
                'a[href$=".pdf"]',
                'a[href*="SpecSheet"]',
                'a[href*="upload"]',
            ]

            for selector in selectors:
                try:
                    pdf_link = page.query_selector(selector)
                    if pdf_link:
                        href = pdf_link.get_attribute("href")
                        if href:
                            # Make absolute URL if relative
                            if href.startswith("/"):
                                href = f"https://www.lodes.com{href}"
                            logger.info(f"Found PDF datasheet link: {href}")
                            return {"Datasheet URL": href}
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Failed to extract PDF link: {e}")
        return {}

    def _extract_installation_manual_url(self, page: Page) -> str:
        """Extract installation manual PDF URL (different from datasheet).

        Looks for links containing:
        - "Istruzioni montaggio" (Italian)
        - "Montageanleitung" (German)
        - "Installation", "Assembly" (English)
        - href patterns with "montage", "installation"

        Returns:
            Installation manual URL or empty string
        """
        selectors = [
            'a[data-name="Istruzioni montaggio"]',  # Lodes-specific (Italian)
            'a.bottone.white-button:has-text("Istruzioni")',
            'a:has-text("Montageanleitung")',  # German
            'a:has-text("Installation")',
            'a:has-text("Assembly")',
            'a[href*="montage"]',
            'a[href*="installation"]',
            'a[href*="istruzioni"]',  # Italian pattern
        ]

        for selector in selectors:
            try:
                link = page.query_selector(selector)
                if link:
                    href = link.get_attribute("href")
                    if href:
                        # Make absolute URL if relative
                        if href.startswith("/"):
                            href = f"https://www.lodes.com{href}"
                        logger.info(f"Found installation manual link: {href}")
                        return href
            except Exception:
                continue

        return ""

    def _extract_cable_length(self, page: Page) -> str:
        """Extract cable/rope length from product specifications.

        Looks for patterns like:
        - "max 250cm"
        - "Seillänge: 300 cm"

        Returns:
            Cable length string (e.g., "max 250cm") or empty string
        """
        try:
            # Check secondary info section
            secondary = page.query_selector("div.secondary-info")
            if secondary:
                text = secondary.text_content()
                # Look for patterns like "max 250cm", "Seillänge: 300 cm"
                match = re.search(r"(?:max\s+)?(\d+)\s*cm", text, re.IGNORECASE)
                if match:
                    return f"max {match.group(1)}cm"

            # Check all table cells for cable/rope length
            tables = page.query_selector_all("table")
            for table in tables:
                cells = table.query_selector_all("td, th")
                for cell in cells:
                    text = cell.text_content()
                    if "seil" in text.lower() or "cable" in text.lower():
                        match = re.search(r"(?:max\s+)?(\d+)\s*cm", text, re.IGNORECASE)
                        if match:
                            return f"max {match.group(1)}cm"

        except Exception as e:
            logger.warning(f"Failed to extract cable length: {e}")

        return ""

    def _extract_dimensions_and_kelvin(self, page: Page) -> dict[str, str]:
        """Extract dimensions and Kelvin temperature from variant table cells.

        Searches table cells for:
        - Dimensions (e.g., "910x60mm", "100x50x30cm")
        - Kelvin temperature (e.g., "2700K", "3000°K")

        Returns:
            Dictionary with 'Dimensions' and 'Kelvin' keys if found
        """
        extracted = {}

        try:
            # Expand technical sheet dropdown to ensure table is visible
            self._expand_technical_sheet_dropdown(page)

            # Get all table cells (both headers and body cells)
            variant_tables = page.query_selector_all("table.table-variante")

            for table in variant_tables:
                # Check all cells in the table
                all_cells = table.query_selector_all("th, td")

                for cell in all_cells:
                    cell_text = cell.text_content()
                    if not cell_text:
                        continue

                    cell_text = cell_text.strip()

                    # Try to extract dimensions
                    if "Dimensions" not in extracted:
                        dimensions = parse_dimensions_from_text(cell_text)
                        if dimensions:
                            extracted["Dimensions"] = cell_text
                            logger.info(f"Found dimensions: {cell_text}")

                    # Try to extract Kelvin temperature
                    # Look for cells containing "K" or "°K" with 4-digit numbers
                    if "Kelvin" not in extracted:
                        kelvin = parse_kelvin_from_text(cell_text)
                        if kelvin:
                            # Store the full text context, will be parsed later
                            extracted["Kelvin"] = kelvin
                            logger.info(f"Found Kelvin: {kelvin}")

            # Also check secondary-info and description for dimensions
            if "Dimensions" not in extracted:
                secondary_info = page.query_selector("div.secondary-info")
                if secondary_info:
                    info_text = secondary_info.text_content()
                    if info_text:
                        dimensions = parse_dimensions_from_text(info_text)
                        if dimensions:
                            extracted["Dimensions"] = info_text.strip()

        except Exception as e:
            logger.warning(f"Failed to extract dimensions and Kelvin: {e}")

        return extracted

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

    def _map_color_name_to_code(self, color_text: str) -> str | None:
        """Map scraped color name to price list color code.

        Args:
            color_text: Color name or text (e.g., "Nero Opaco – 9005", "Bianco Opaco")

        Returns:
            Color code (e.g., "2000") or None if not found
        """
        if not color_text:
            return None

        # Clean and normalize the text
        text_lower = color_text.lower().strip()
        # Remove color code suffixes like "– 9005"
        text_lower = re.sub(r"\s*[–-]\s*\d+", "", text_lower)

        # Check exact match first
        if text_lower in self.COLOR_NAME_TO_CODE:
            return self.COLOR_NAME_TO_CODE[text_lower]

        # Check partial matches (for phrases like "nero opaco" in longer text)
        for color_name, code in self.COLOR_NAME_TO_CODE.items():
            if color_name in text_lower:
                return code

        logger.warning(f"Could not map color name to code: {color_text}")
        return None

    @staticmethod
    def _extract_variation_attribute_names(variants: list[dict[str, str]]) -> set[str]:
        """Extract attribute names that vary across product variants.

        Args:
            variants: List of variant dictionaries

        Returns:
            Set of attribute names (excluding "Code"/"Codice" fields)
        """
        variation_attr_names = set()
        for variant in variants:
            variation_attr_names.update(variant.keys())

        # Remove SKU/Code fields (case-insensitive)
        attrs_to_remove = {
            attr for attr in variation_attr_names if attr.lower() in ["code", "codice"]
        }
        variation_attr_names -= attrs_to_remove

        return variation_attr_names

    def _find_matching_price_list_product(
        self, url_slug: SKU, variants: list[dict[str, str]]
    ) -> tuple[dict | None, SKU]:
        """Find matching price list product for scraped variants.

        Args:
            url_slug: Original URL slug (e.g., "kelly")
            variants: List of scraped variant dictionaries

        Returns:
            Tuple of (price_list_product, actual_parent_sku)
            Returns (None, url_slug) if no price list match found
        """
        price_list_products = lodes_price_list.get_product_by_slug(url_slug)

        if not price_list_products:
            return None, url_slug

        # For products with multiple sizes (e.g., Kelly dome 50/60/80),
        # match based on size keywords in variant headers
        size_keywords = {
            "small": ["small", "50"],
            "medium": ["medium", "60"],
            "large": ["large", "80"],
        }

        for variant in variants:
            for key in variant.keys():
                key_lower = key.lower()
                # Determine which size this variant represents
                variant_size = None
                for size_name, keywords in size_keywords.items():
                    if any(kw in key_lower for kw in keywords):
                        variant_size = size_name
                        break

                if not variant_size:
                    continue

                # Match to price list product with same size
                for pl_product in price_list_products:
                    product_name_lower = pl_product["product_name"].lower()
                    # Check if product name contains the same size keywords
                    size_match = any(
                        kw in product_name_lower for kw in size_keywords[variant_size]
                    )
                    if size_match:
                        actual_sku = SKU(pl_product["base_sku"])
                        logger.info(
                            f"Matched variant '{key}' to price list product '{pl_product['product_name']}'"
                        )
                        return pl_product, actual_sku

        # No specific match found, use first price list product
        pl_product = price_list_products[0]
        actual_sku = SKU(pl_product["base_sku"])
        logger.info(f"Using first price list product: {pl_product['product_name']}")
        return pl_product, actual_sku

    @staticmethod
    def _extract_color_code_from_sku(sku: str) -> str | None:
        """Extract color code from product SKU.

        Args:
            sku: Full SKU (e.g., "14126 1000")

        Returns:
            Color code (e.g., "1000") or None if invalid format
        """
        if not sku:
            return None

        parts = sku.split()
        return parts[1] if len(parts) >= 2 else None

    def _filter_variants_by_base_sku(
        self, variants: list[dict[str, str]], base_sku: str
    ) -> list[dict[str, str]]:
        """Filter variants to only include those matching base SKU.

        When scraping products like "kelly", the page shows ALL Kelly products
        (small dome 50, medium dome 60, large dome 80, etc.) with variant tables
        for each. This filters to only variants belonging to the target product.

        Args:
            variants: All scraped variants from the page
            base_sku: Base SKU to match (e.g., "14126")

        Returns:
            Filtered list of variants matching the base SKU
        """
        filtered_variants = []

        for variant in variants:
            variant_code = (
                variant.get("Code")
                or variant.get("Codice")
                or variant.get("code")
                or variant.get("codice")
                or ""
            )

            # Include variant if its SKU starts with base_sku
            if variant_code.startswith(base_sku):
                filtered_variants.append(variant)

        return filtered_variants

    def _enrich_attributes_with_price_list(
        self,
        attributes: dict[str, str],
        cable_length: str,
        price_list_product: dict | None,
    ) -> tuple[dict[str, str], str]:
        """Enrich product attributes with price list data.

        Args:
            attributes: Existing product attributes
            cable_length: Existing cable length (may be empty)
            price_list_product: Price list product data or None

        Returns:
            Tuple of (enriched_attributes, cable_length)
        """
        if not price_list_product:
            return attributes, cable_length

        # Override cable_length from price list if not already set
        if not cable_length and price_list_product.get("cable_length"):
            cable_length = price_list_product["cable_length"]

        # Add price list fields to attributes
        enriched_attrs = attributes.copy()
        if price_list_product.get("light_source"):
            enriched_attrs["Light source"] = price_list_product["light_source"]
        if price_list_product.get("dimmability"):
            enriched_attrs["Dimmbarkeit"] = price_list_product["dimmability"]
        if price_list_product.get("voltage"):
            enriched_attrs["Voltage"] = price_list_product["voltage"]

        return enriched_attrs, cable_length

    def _map_variant_to_price_list(
        self, variant: dict[str, str], price_list_product: dict | None
    ) -> tuple[str | None, float | None]:
        """Map scraped variant to price list SKU and price.

        Args:
            variant: Scraped variant data dictionary
            price_list_product: Price list product data or None

        Returns:
            Tuple of (variant_sku, variant_price)
            Returns (None, None) if no price list mapping found
        """
        if not price_list_product:
            return None, None

        # First, try to extract color code directly from variant SKU (e.g., "14126 1000" -> "1000")
        variant_code = (
            variant.get("Code")
            or variant.get("Codice")
            or variant.get("code")
            or variant.get("codice")
        )
        if variant_code:
            color_code = self._extract_color_code_from_sku(variant_code)
            if color_code:
                # Find matching variant in price list
                for pl_variant in price_list_product["variants"]:
                    if pl_variant["color_code"] == color_code:
                        variant_sku = pl_variant["sku"]
                        variant_price = pl_variant["price_eur"]
                        logger.info(
                            f"Matched variant code {variant_code} to price list: {variant_sku} @ {variant_price} EUR"
                        )
                        return variant_sku, variant_price

        # Fallback: Find matching color in variant data attributes
        for attr_name, attr_value in variant.items():
            if not attr_value:
                continue

            # Try to map this attribute to a color code
            color_code = self._map_color_name_to_code(attr_value)
            if not color_code:
                continue

            logger.info(f"Mapped '{attr_value}' to color code '{color_code}'")

            # Find matching variant in price list
            for pl_variant in price_list_product["variants"]:
                if pl_variant["color_code"] == color_code:
                    variant_sku = pl_variant["sku"]
                    variant_price = pl_variant["price_eur"]
                    logger.info(
                        f"Matched to price list variant: {variant_sku} @ {variant_price} EUR"
                    )
                    return variant_sku, variant_price

        return None, None

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

        Uses Code if available, otherwise uses 1-2 key variation attributes.

        Args:
            base_name: Parent product name
            variant: Variant data dict
            variation_attr_names: Set of variation attribute names
            idx: Variant index (for fallback naming)

        Returns:
            Formatted variation name (e.g., "Kelly 14126 1000" or "Kelly Matte White")
        """
        # Priority 1: Use Code/Codice if available
        code = (
            variant.get("Code")
            or variant.get("Codice")
            or variant.get("code")
            or variant.get("codice")
        )
        if code:
            return f"{base_name} {code}"

        # Priority 2: Use first 1-2 meaningful attributes (excluding variant type/group names)
        # Prioritize color/finish attributes like "Armatur", "Structure", "Diffusor"
        priority_attrs = ["Armatur", "Structure", "Diffusor", "Color", "Finish"]

        variant_details = []
        for attr_name in priority_attrs:
            if attr_name in variant and variant[attr_name]:
                variant_details.append(variant[attr_name])
                if len(variant_details) >= 2:
                    break

        # If no priority attributes found, use any available attributes (max 2)
        if not variant_details:
            for attr_name in sorted(variation_attr_names):
                if attr_name in variant and variant[attr_name]:
                    variant_details.append(variant[attr_name])
                    if len(variant_details) >= 2:
                        break

        if variant_details:
            return f"{base_name} {' '.join(variant_details)}"

        return f"{base_name} Variant {idx+1}"

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
        dimensions: dict[str, float] | None,
        light_specs: dict[str, str] | None,
        installation_manual: str,
        cable_length: str,
        scraped_lang: str,
        url_slug: SKU,
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
            dimensions: Product dimensions (length, width, height in cm)
            light_specs: Light specifications (kelvin, wattage, lumen)
            installation_manual: URL to installation manual
            cable_length: Cable/rope length specification
            scraped_lang: Language code
            url_slug: Original URL slug used to scrape product

        Returns:
            List with 1 parent + N child variation ProductData objects
        """
        if not variants:
            return []

        # Find matching price list product
        price_list_product, actual_parent_sku = self._find_matching_price_list_product(
            url_slug, variants
        )

        # Filter variants to only include those belonging to this specific product
        # (e.g., when scraping "kelly", page shows 14126, 14127, 14128 variants,
        # but we only want 14126 variants)
        if actual_parent_sku:
            filtered_variants = self._filter_variants_by_base_sku(
                variants, str(actual_parent_sku)
            )

            if filtered_variants:
                logger.info(
                    f"Filtered {len(variants)} total variants to {len(filtered_variants)} "
                    f"matching base SKU {actual_parent_sku}"
                )
                variants = filtered_variants
            else:
                logger.warning(
                    f"No variants match base SKU {actual_parent_sku}, keeping all variants"
                )

        # Enrich attributes with price list data
        attributes, cable_length = self._enrich_attributes_with_price_list(
            attributes, cable_length, price_list_product
        )

        variation_attr_names = self._extract_variation_attribute_names(variants)
        parent_variation_attrs = self._build_parent_variation_attributes(
            variants, variation_attr_names
        )

        # For price list products, aggregate all color names in German
        available_colors = None
        parent_name = name
        if price_list_product:
            available_colors = lodes_price_list.get_all_product_colors(price_list_product)
            # Use price list product name for accurate naming (e.g., "Kelly small dome 50")
            parent_name = price_list_product["product_name"]
            # Use price list dimensions if available (more accurate than scraped)
            if price_list_product.get("dimensions"):
                dimensions = price_list_product["dimensions"]
                logger.info(f"Using price list dimensions: {dimensions}")

        parent = ProductData(
            sku=actual_parent_sku,  # Use actual SKU from price list
            name=parent_name,
            description=description,
            manufacturer=self.config.manufacturer,
            categories=categories,
            attributes=attributes,
            images=images,
            product_type="variable",
            weight=weight_kg,
            dimensions=dimensions,
            light_specs=light_specs,
            datasheet_url=attributes.get("Datasheet URL"),
            installation_manual_url=installation_manual,
            cable_length=cable_length,
            available_colors=available_colors,
            product_notes="Leuchtmittel nicht inkludiert.",
            scraped_language=scraped_lang,
            variation_attributes=parent_variation_attrs,
            original_name=parent_name if price_list_product else None,
        )

        children = []
        for idx, variant in enumerate(variants):
            # Map variant to price list SKU and price
            variant_sku, variant_price = self._map_variant_to_price_list(
                variant, price_list_product
            )

            # Fallback to scraped SKU if price list mapping failed
            if not variant_sku:
                variant_sku = (
                    variant.get("Code")
                    or variant.get("Codice")
                    or variant.get("code")
                    or variant.get("codice")
                    or f"{actual_parent_sku}-{idx+1}"
                )

            variant_name = self._build_variation_name(
                parent_name, variant, variation_attr_names, idx
            )

            child_variation_attrs = {
                attr_name: variant[attr_name]
                for attr_name in variation_attr_names
                if attr_name in variant and variant[attr_name]
            }

            # Enrich variation attributes with color name from price list
            if price_list_product and variant_sku:
                color_code = self._extract_color_code_from_sku(variant_sku)
                if color_code:
                    # Find matching color in price list
                    for pl_variant in price_list_product["variants"]:
                        if pl_variant["color_code"] == color_code:
                            # Add German color name to variation attributes
                            child_variation_attrs["Farbe"] = pl_variant["color_name_de"]
                            break

            child = ProductData(
                sku=SKU(variant_sku),
                name=variant_name,
                description="",
                manufacturer=self.config.manufacturer,
                categories=categories,  # Inherit parent's categories for Produkttyp inference
                attributes={},
                images=[],
                product_type="variation",
                parent_sku=actual_parent_sku,
                variation_attributes=child_variation_attrs,
                regular_price=variant_price,  # Set price from price list
                weight=weight_kg,
                dimensions=dimensions,
                light_specs=light_specs,
                installation_manual_url=installation_manual,
                cable_length=cable_length,
                product_notes="Leuchtmittel nicht inkludiert.",
                scraped_language=scraped_lang,
                original_name=parent_name if price_list_product else None,
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
        seen_codes = set()  # Track seen product codes to avoid duplicates

        variant_tables = page.query_selector_all("table.table-variante")

        for table in variant_tables:
            header_map = self._build_header_index_map(table)
            rows = table.query_selector_all("tbody tr")

            for row in rows:
                variant_data = self._parse_variant_row(row, header_map)
                if variant_data:
                    # Deduplicate by Code/Codice if present
                    code = (
                        variant_data.get("Code")
                        or variant_data.get("Codice")
                        or variant_data.get("code")
                        or variant_data.get("codice")
                    )
                    if code:
                        if code in seen_codes:
                            continue  # Skip duplicate
                        seen_codes.add(code)

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

        Detects product codes (e.g., "14126 1000") and stores them as "Code".

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
                    cleaned_value = attr_value.strip()

                    # Check if this value looks like a product code
                    if re.match(self.PRODUCT_CODE_PATTERN, cleaned_value):
                        variant_data["Code"] = cleaned_value
                    else:
                        variant_data[attr_name] = cleaned_value

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
