"""Vibia.com product scraper implementation.

Following CLAUDE.md: manufacturer-specific logic only, inherits common functionality.
Vibia uses Next.js with JSON-LD embedded data, requiring different extraction approach than Lodes.
"""

import os
import re
import zipfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.scrapers.base_scraper import BaseScraper
from src.models import SKU, ImageUrl, Manufacturer, ProductData, ScraperConfig
from src import vibia_price_list
from src.auth import VibiaAuth


class VibiaScraper(BaseScraper):
    """Scraper for Vibia.com product pages."""

    def __init__(self):
        """Initialize Vibia scraper with default configuration."""
        config = ScraperConfig(
            manufacturer=Manufacturer("vibia"),
            base_url="https://www.vibia.com",
            rate_limit_delay=1.0,
            max_retries=3,
            timeout=30,
            language_priority=["de", "en"],  # Try German first, fall back to English
            default_price=0.0,
        )
        super().__init__(config)
        self.vibia_auth: Optional[VibiaAuth] = None

    def build_product_url(self, sku: SKU, language: str = "de") -> str:
        """Construct product URL from SKU with language support.

        Args:
            sku: Product identifier (model number, simplified SKU, or slug)
            language: Language code (e.g., "de", "en")

        Returns:
            Full product URL

        Examples:
            >>> build_product_url("0162", "de")
            'https://www.vibia.com/de/int/kollektionen/pendelleuchten-circus-pendelleuchte'
            >>> build_product_url("circus", "de")
            'https://www.vibia.com/de/int/kollektionen/pendelleuchten-circus-pendelleuchte'
        """
        # Parse SKU to extract model or slug
        slug = self._extract_slug_from_sku(sku)

        if not slug:
            raise ValueError(f"Could not determine product slug from SKU: {sku}")

        # Get category prefix from price list
        category = vibia_price_list.get_category_for_slug(slug)
        if not category:
            logger.warning(
                f"No category found for slug '{slug}', using default 'pendelleuchten'"
            )
            category = "pendelleuchten"

        # Get product type suffix (e.g., "pendelleuchte", "wandleuchte")
        products = vibia_price_list.get_product_by_slug(slug)
        product_type = (
            products[0]["product_type_suffix"] if products else "pendelleuchte"
        )

        # Construct URL: /{lang}/int/kollektionen/{category}-{slug}-{type}
        return f"{self.config.base_url}/{language}/int/kollektionen/{category}-{slug}-{product_type}"

    def _extract_slug_from_sku(self, sku: SKU) -> str | None:
        """Extract product slug from SKU.

        Args:
            sku: Product SKU (can be model number, simplified SKU, or slug)

        Returns:
            URL slug or None if not found
        """
        # If it's already a slug (alphabetic), return as-is
        if re.match(r"^[a-z-]+$", sku):
            return sku

        # Parse SKU components
        components = vibia_price_list.parse_sku_components(sku)
        if components and "model" in components:
            model = components["model"]
            product = vibia_price_list.get_product_by_model(model)
            if product:
                return product["url_slug"]

        # Try extracting first 4 digits as model number
        model_match = re.match(r"^(\d{4})", sku)
        if model_match:
            model = model_match.group(1)
            product = vibia_price_list.get_product_by_model(model)
            if product:
                return product["url_slug"]

        return None

    def _ensure_browser(self) -> None:
        """Ensure browser is initialized and ready for use."""
        if self._page is None:
            self.setup_browser()
        assert self._page is not None

    def scrape_product(self, sku: SKU) -> list[ProductData]:
        """Scrape product data from Vibia website.

        Args:
            sku: Product identifier (model number, simplified SKU, or slug)

        Returns:
            List of ProductData objects (parent + variants if applicable)

        Raises:
            Exception: If scraping fails
        """
        self._ensure_browser()
        assert self._page is not None

        logger.info(f"Scraping Vibia product: {sku}")

        # Try each language in priority order
        for language in self.config.language_priority or ["de"]:
            try:
                url = self.build_product_url(sku, language)
                logger.debug(f"Attempting URL: {url}")

                self._page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.config.timeout * 1000,
                )
                self._page.wait_for_load_state("networkidle", timeout=10000)

                # Extract JSON data from Next.js page
                json_data = self._extract_json_data(self._page)

                if not json_data:
                    logger.warning(f"No JSON data found at {url}, trying next language")
                    continue

                # Parse product data from JSON
                products = self._parse_product_data(json_data, sku, language)

                if products:
                    logger.success(
                        f"Successfully scraped {len(products)} product(s) from {url}"
                    )

                    # Download product files if credentials are available
                    try:
                        feature_props = (
                            json_data.get("props", {})
                            .get("pageProps", {})
                            .get("featureProps", {})
                        )

                        if feature_props:
                            # Use parent SKU as output directory name
                            base_sku = products[0].sku if products else sku
                            output_dir = Path("output") / str(base_sku)

                            # Download files (manual and specSheet by default)
                            self.download_product_files(
                                feature_props=feature_props,
                                output_dir=output_dir,
                                download_types=["manual", "specSheet"],
                            )
                    except Exception as e:
                        logger.warning(f"File download failed: {e}")
                        # Continue anyway - downloads are optional

                    return products

            except PlaywrightTimeout as e:
                logger.warning(f"Timeout loading {url}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                continue

        raise Exception(f"Failed to scrape product {sku} in all languages")

    def _extract_json_data(self, page: Page) -> dict[str, Any] | None:
        """Extract JSON-LD or Next.js data from page.

        Args:
            page: Playwright Page instance

        Returns:
            JSON data dictionary or None if not found
        """
        try:
            # Try extracting __NEXT_DATA__ from Next.js
            json_data = page.evaluate("() => window.__NEXT_DATA__")
            if json_data:
                logger.debug("Extracted __NEXT_DATA__ from page")
                return json_data
        except Exception as e:
            logger.debug(f"Could not extract __NEXT_DATA__: {e}")

        try:
            # Try extracting from script tags with type="application/ld+json"
            json_ld = page.evaluate(
                """
                () => {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const script of scripts) {
                        try {
                            return JSON.parse(script.textContent);
                        } catch (e) {
                            continue;
                        }
                    }
                    return null;
                }
                """
            )
            if json_ld:
                logger.debug("Extracted JSON-LD data from page")
                return json_ld
        except Exception as e:
            logger.debug(f"Could not extract JSON-LD: {e}")

        return None

    def _parse_product_data(
        self, json_data: dict[str, Any], sku: SKU, language: str
    ) -> list[ProductData]:
        """Parse product data from JSON structure.

        Args:
            json_data: JSON data extracted from page
            sku: Original SKU requested
            language: Language code used

        Returns:
            List of ProductData objects
        """
        try:
            # Extract product info from Next.js data structure
            # Vibia uses: props.pageProps.featureProps.data
            props = json_data.get("props", {})
            page_props = props.get("pageProps", {})
            feature_props = page_props.get("featureProps", {})

            # Get the main product data
            product_data = feature_props.get("data", {})

            # Get product info from price list
            slug = self._extract_slug_from_sku(sku)
            price_list_products = (
                vibia_price_list.get_product_by_slug(slug) if slug else []
            )

            # Parse name from JSON or use price list
            name = self._extract_product_name(product_data, price_list_products)

            # Parse description
            description = self._extract_description(product_data)

            # Parse images
            images = self._extract_images(product_data)

            # Parse attributes
            attributes = self._extract_attributes(product_data, price_list_products)

            # Parse categories (needs access to both data and collection)
            categories = self._extract_categories_from_feature_props(feature_props)

            # Create product data list (handle variants)
            products = self._create_products_with_variants(
                sku=sku,
                name=name,
                description=description,
                images=images,
                attributes=attributes,
                categories=categories,
                price_list_products=price_list_products,
            )

            return products

        except Exception as e:
            logger.error(f"Error parsing product data: {e}")
            raise

    def _extract_product_name(
        self, json_data: dict[str, Any], price_list_products: list[Any]
    ) -> str:
        """Extract product name from JSON data or price list."""
        # Try JSON data first
        name = (
            json_data.get("name")
            or json_data.get("title")
            or json_data.get("data", {}).get("name")
        )

        if name:
            return str(name)

        # Fallback to price list
        if price_list_products:
            return price_list_products[0]["product_name"]

        return "Unknown Product"

    def _extract_description(self, json_data: dict[str, Any]) -> str:
        """Extract product description from JSON data."""
        # Vibia stores description in technicalInfo.description as array of paragraph objects
        tech_info = json_data.get("technicalInfo", {})
        description_list = tech_info.get("description", [])

        if isinstance(description_list, list):
            # Extract paragraph text from each object
            paragraphs = []
            for item in description_list:
                if isinstance(item, dict):
                    para = item.get("paragraph", "")
                    if para:
                        paragraphs.append(str(para))
                elif isinstance(item, str):
                    paragraphs.append(item)
            return "\n\n".join(paragraphs)
        elif isinstance(description_list, str):
            return description_list

        return ""

    def _extract_images(self, json_data: dict[str, Any]) -> list[ImageUrl]:
        """Extract product images from JSON data."""
        images: list[ImageUrl] = []

        # Extract from hero.media (desktop, tablet, mobile)
        hero = json_data.get("hero", {})
        media = hero.get("media", {})

        for variant in ["desktop", "tablet", "mobile"]:
            variant_data = media.get(variant, {})
            url = variant_data.get("url")
            if url:
                # Ensure full URL
                if url.startswith("//"):
                    url = f"https:{url}"
                elif url.startswith("/"):
                    url = f"{self.config.base_url}{url}"
                images.append(ImageUrl(url))
                break  # Only take the first available image

        # Fallback: try strapiMedia if no hero images found
        if not images:
            strapi_media = json_data.get("strapiMedia", [])
            if isinstance(strapi_media, list):
                for img in strapi_media:
                    if isinstance(img, dict):
                        url = (
                            img.get("url")
                            or img.get("large", {}).get("url")
                            or img.get("medium", {}).get("url")
                        )
                        if url:
                            if url.startswith("//"):
                                url = f"https:{url}"
                            elif url.startswith("/"):
                                url = f"{self.config.base_url}{url}"
                            images.append(ImageUrl(url))

        return images[:10]  # Limit to 10 images

    def _extract_attributes(
        self, json_data: dict[str, Any], price_list_products: list[Any]
    ) -> dict[str, str]:
        """Extract product attributes from JSON data and price list."""
        attributes: dict[str, str] = {}

        # Extract from JSON
        attrs = json_data.get("attributes") or json_data.get("specs") or {}

        if isinstance(attrs, dict):
            for key, value in attrs.items():
                if isinstance(value, (str, int, float)):
                    attributes[key] = str(value)

        # Add attributes from price list
        if price_list_products:
            product = price_list_products[0]
            attributes["Designer"] = product.get("designer", "")
            attributes["Voltage"] = product.get("voltage", "")
            attributes["IP Rating"] = product.get("ip_rating", "")

            # Add dimensions
            dims = product.get("dimensions")
            if dims:
                if "diameter" in dims:
                    attributes["Diameter"] = f"{dims['diameter']} cm"
                if "height" in dims:
                    attributes["Height"] = f"{dims['height']} cm"
                if "length" in dims:
                    attributes["Length"] = f"{dims['length']} cm"

        return attributes

    def _extract_categories_from_feature_props(
        self, feature_props: dict[str, Any]
    ) -> list[str]:
        """Extract product categories from featureProps structure."""
        categories: list[str] = []

        # Extract from data.hero.applicationBreadcrumb
        product_data = feature_props.get("data", {})
        hero = product_data.get("hero", {})
        breadcrumb = hero.get("applicationBreadcrumb", [])

        if isinstance(breadcrumb, list):
            for item in breadcrumb:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        categories.append(str(text))
                elif isinstance(item, str):
                    categories.append(item)

        # Also add collection family from featureProps.collection
        collection = feature_props.get("collection", {})
        if isinstance(collection, dict):
            family = collection.get("family") or collection.get("name")
            if family and family not in categories:
                categories.append(str(family))

        return categories

    def _create_products_with_variants(
        self,
        sku: SKU,
        name: str,
        description: str,
        images: list[ImageUrl],
        attributes: dict[str, str],
        categories: list[str],
        price_list_products: list[Any],
    ) -> list[ProductData]:
        """Create ProductData objects with variant support."""
        products: list[ProductData] = []

        # Get variants from price list
        all_variants = []
        for price_product in price_list_products:
            all_variants.extend(price_product["variants"])

        # Extract dimensions and other data from price list
        dimensions = None
        cable_length = None
        ip_rating = attributes.get("IP Rating", "")
        voltage = attributes.get("Voltage", "")

        if price_list_products:
            product_info = price_list_products[0]

            # Extract dimensions (diameter -> length/width, height -> height)
            dims = product_info.get("dimensions")
            if dims:
                if "diameter" in dims:
                    # For circular products, diameter becomes both length and width
                    diameter = dims["diameter"]
                    dimensions = {
                        "length": diameter,
                        "width": diameter,
                        "height": dims.get("height", diameter),
                    }
                elif "length" in dims and "width" in dims and "height" in dims:
                    dimensions = {
                        "length": dims["length"],
                        "width": dims["width"],
                        "height": dims["height"],
                    }

            # Extract cable length if available
            if "cable_length_cm" in product_info:
                cable_length = f"{product_info['cable_length_cm']} cm"

        if not all_variants:
            # Create simple product without variants
            products.append(
                ProductData(
                    sku=sku,
                    name=name,
                    description=description,
                    manufacturer=self.config.manufacturer,
                    categories=categories,
                    attributes=attributes,
                    images=images,
                    product_type="simple",
                    regular_price=self.config.default_price,
                    dimensions=dimensions,
                    cable_length=cable_length,
                    ip_rating=ip_rating,
                )
            )
            return products

        # Create variable product (parent)
        parent_sku = self._get_base_sku(sku)
        products.append(
            ProductData(
                sku=SKU(parent_sku),
                name=name,
                description=description,
                manufacturer=self.config.manufacturer,
                categories=categories,
                attributes=attributes,
                images=images,
                product_type="variable",
                dimensions=dimensions,
                cable_length=cable_length,
                ip_rating=ip_rating,
            )
        )

        # Create variant products (children)
        for variant in all_variants:
            variant_sku = SKU(variant["sku"])
            variant_name = f"{name} - {variant['led_name_en']}"

            # Map variation attributes to keys that CSV exporter recognizes
            variation_attrs = {
                "Color": variant["surface_name_en"],  # Maps to "Farbe"
                "Dali": variant["control_name_en"],   # Maps to "Dimmbarkeit"
                "Mounting": "Aufbaubaldachin",        # Standard mounting type for pendant lights
            }

            products.append(
                ProductData(
                    sku=variant_sku,
                    name=variant_name,
                    description=description,
                    manufacturer=self.config.manufacturer,
                    categories=categories,
                    attributes=attributes,
                    images=images,
                    product_type="variation",
                    parent_sku=SKU(parent_sku),
                    variation_attributes=variation_attrs,
                    regular_price=variant["price_eur"],
                    dimensions=dimensions,
                    cable_length=cable_length,
                    ip_rating=ip_rating,
                )
            )

        return products

    def _get_base_sku(self, sku: SKU) -> str:
        """Extract base SKU (model number) from any SKU format."""
        components = vibia_price_list.parse_sku_components(sku)
        if components and "model" in components:
            return components["model"]

        # Try extracting first 4 digits
        model_match = re.match(r"^(\d{4})", sku)
        if model_match:
            return model_match.group(1)

        # Try getting from slug
        slug = self._extract_slug_from_sku(sku)
        if slug:
            products = vibia_price_list.get_product_by_slug(slug)
            if products:
                return products[0]["base_sku"]

        return sku

    def scrape_category(self, category_url: str) -> list[SKU]:
        """Discover all product SKUs from a Vibia category/collection page.

        Args:
            category_url: URL of category/collection page

        Returns:
            List of discovered product SKUs

        Note:
            This is a placeholder implementation. Would need to analyze
            Vibia's category page structure to implement fully.
        """
        self._ensure_browser()
        assert self._page is not None

        logger.info(f"Scraping Vibia category: {category_url}")

        # TODO: Implement category scraping
        # Would need to:
        # 1. Load category page
        # 2. Scroll to load all products (if infinite scroll)
        # 3. Extract product links
        # 4. Parse SKUs/slugs from links

        logger.warning("Category scraping not yet implemented for Vibia")
        return []

    def _extract_download_ids(
        self, feature_props: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Extract IDs needed for downloading documents from Vibia API.

        Args:
            feature_props: featureProps object from __NEXT_DATA__

        Returns:
            Dictionary with catalogId, familyId, subFamilyId, applicationLocationId
            or None if required fields are missing
        """
        try:
            data = feature_props.get("data", {})
            collection = feature_props.get("collection", {})

            catalog_id = data.get("id")
            if not catalog_id:
                logger.warning("No catalog ID found in product data")
                return None

            # Extract IDs from collection data
            family = collection.get("family", {})
            sub_family = collection.get("subFamily", {})
            applications_locations = collection.get("applicationsLocations", [])

            family_id = family.get("id")
            sub_family_id = sub_family.get("id")

            # Use first application location if available
            application_location_id = None
            if applications_locations and len(applications_locations) > 0:
                application_location_id = applications_locations[0].get("id")

            if not all([family_id, sub_family_id, application_location_id]):
                logger.warning(
                    f"Missing required IDs: family={family_id}, "
                    f"subFamily={sub_family_id}, appLocation={application_location_id}"
                )
                return None

            return {
                "catalog_id": str(catalog_id),
                "model_id": str(catalog_id),
                "family_id": family_id,
                "sub_family_id": sub_family_id,
                "application_location_id": application_location_id,
            }

        except Exception as e:
            logger.error(f"Error extracting download IDs: {e}")
            return None

    def _extract_zip_safely(
        self, zip_ref: zipfile.ZipFile, output_dir: Path
    ) -> None:
        """Safely extract ZIP file with security validation.

        Protects against:
        - Path traversal attacks (e.g., ../../etc/passwd)
        - Zip bombs (excessive decompressed size)

        Args:
            zip_ref: Open ZipFile object
            output_dir: Target extraction directory

        Raises:
            ValueError: If ZIP contains malicious content
        """
        output_dir_resolved = output_dir.resolve()
        max_size = 500 * 1024 * 1024  # 500 MB max total size

        total_size = 0
        for file_info in zip_ref.filelist:
            # Check for path traversal
            member_path = (output_dir / file_info.filename).resolve()
            if not str(member_path).startswith(str(output_dir_resolved)):
                raise ValueError(
                    f"ZIP contains unsafe path: {file_info.filename}"
                )

            # Check for zip bomb
            total_size += file_info.file_size
            if total_size > max_size:
                raise ValueError(
                    f"ZIP decompressed size exceeds limit ({max_size} bytes)"
                )

        # Extract all files (validated as safe)
        zip_ref.extractall(output_dir)

    def download_product_files(
        self,
        feature_props: dict[str, Any],
        output_dir: Path,
        download_types: list[str] = None,
    ) -> bool:
        """Download product files (manuals, datasheets, images) from Vibia.

        Args:
            feature_props: featureProps object from __NEXT_DATA__
            output_dir: Directory to save downloaded files
            download_types: List of file types to download
                Valid types: "manual", "specSheet", "images"
                If None, downloads manual and specSheet by default

        Returns:
            True if download successful, False otherwise
        """
        if download_types is None:
            download_types = ["manual", "specSheet"]

        # Initialize auth if not already done
        if not self.vibia_auth:
            email = os.getenv("VIBIA_EMAIL")
            password = os.getenv("VIBIA_PASSWORD")

            if not email or not password:
                logger.warning(
                    "Vibia credentials not found in environment. "
                    "Skipping file downloads."
                )
                return False

            self.vibia_auth = VibiaAuth(email=email, password=password)
            if not self.vibia_auth.login():
                logger.error("Failed to authenticate with Vibia")
                return False

        # Extract download IDs
        ids = self._extract_download_ids(feature_props)
        if not ids:
            logger.error("Could not extract required IDs for download")
            return False

        try:
            # Download documents
            zip_content = self.vibia_auth.download_documents(
                catalog_id=ids["catalog_id"],
                model_id=ids["model_id"],
                sub_family_id=ids["sub_family_id"],
                application_location_id=ids["application_location_id"],
                family_id=ids["family_id"],
                document_types=download_types,
                lang="en",
            )

            if not zip_content:
                logger.warning("No files downloaded from Vibia")
                return False

            # Save and extract ZIP file
            output_dir.mkdir(parents=True, exist_ok=True)
            zip_path = output_dir / "vibia_documents.zip"

            with open(zip_path, "wb") as f:
                f.write(zip_content)

            logger.info(f"Saved ZIP file to {zip_path}")

            # Extract ZIP contents securely
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Validate ZIP contents before extraction (security check)
                self._extract_zip_safely(zip_ref, output_dir)
                logger.success(
                    f"Extracted {len(zip_ref.namelist())} files to {output_dir}"
                )

            # Optionally remove ZIP file after extraction
            zip_path.unlink()

            return True

        except Exception as e:
            logger.error(f"Error downloading product files: {e}")
            return False
