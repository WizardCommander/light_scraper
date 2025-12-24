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
            # Check for HEADLESS env var (default: True)
            headless = os.getenv("HEADLESS", "true").lower() != "false"
            self.setup_browser(headless=headless)
        assert self._page is not None

    def scrape_product(self, sku: SKU, output_base: str = "output") -> list[ProductData]:
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
                            output_dir = Path(output_base) / str(base_sku)

                            # Download files (manual and specSheet)
                            self.download_product_files(output_dir=output_dir)
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

            # Get product info from price list - filter to specific model
            base_sku = self._get_base_sku(sku)
            price_list_product = vibia_price_list.get_product_by_model(base_sku)
            price_list_products = [price_list_product] if price_list_product else []

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

        # Check if user requested a specific variant (e.g., "0162 24/9Z" or "0162/9Z")
        requested_surface_code = None
        requested_control_code = None
        if "/" in sku:
            # Parse SKU format: "0162 24/9Z" or "0162/9Z"
            # Format: model [surface]/control
            parts = sku.split("/")
            if len(parts) == 2:
                requested_control_code = parts[1].strip()  # "9Z"

                # Extract surface code if present (appears before /)
                before_slash = parts[0].strip()  # "0162 24" or "0162"
                model_and_surface = before_slash.split()
                if len(model_and_surface) == 2:
                    requested_surface_code = model_and_surface[1]  # "24"

                logger.debug(
                    f"Filtering to variant - surface: {requested_surface_code or 'any'}, "
                    f"control: {requested_control_code}"
                )

        # Get variants from price list
        all_variants = []
        for price_product in price_list_products:
            all_variants.extend(price_product["variants"])

        # Filter variants if specific one was requested
        if requested_control_code:
            filtered_variants = []
            for v in all_variants:
                # Match control code (e.g., "9Z") - case-insensitive
                control_match = v[
                    "control_code"
                ].upper() == requested_control_code.upper() or v[
                    "sku"
                ].upper().endswith(
                    f"/{requested_control_code.upper()}"
                )

                # Match surface code if specified (e.g., "24")
                surface_match = True
                if requested_surface_code:
                    surface_match = v["surface_code"] == requested_surface_code

                if control_match and surface_match:
                    filtered_variants.append(v)

            if not filtered_variants:
                logger.warning(
                    f"Requested variant (surface={requested_surface_code}, control={requested_control_code}) "
                    f"not found in price list"
                )
            else:
                logger.info(f"Filtered to {len(filtered_variants)} variant(s)")

            all_variants = filtered_variants

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

        # If user requested a specific variant and we found exactly one, return it as simple product
        if requested_control_code and len(all_variants) == 1:
            variant = all_variants[0]
            variant_name = f"{name} - {variant['led_name_en']}"

            variation_attrs = {
                "Color": variant["surface_name_en"],
                "Dali": variant["control_name_en"],
                "Mounting": "Aufbaubaldachin",
            }

            products.append(
                ProductData(
                    sku=SKU(variant["sku"]),
                    name=variant_name,
                    description=description,
                    manufacturer=self.config.manufacturer,
                    categories=categories,
                    attributes={**attributes, **variation_attrs},  # Merge variant attrs
                    images=images,
                    product_type="simple",  # Simple product, not variation
                    regular_price=variant["price_eur"],
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
                "Dali": variant["control_name_en"],  # Maps to "Dimmbarkeit"
                "Mounting": "Aufbaubaldachin",  # Standard mounting type for pendant lights
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

    def _extract_zip_safely(self, zip_ref: zipfile.ZipFile, output_dir: Path) -> None:
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
                raise ValueError(f"ZIP contains unsafe path: {file_info.filename}")

            # Check for zip bomb
            total_size += file_info.file_size
            if total_size > max_size:
                raise ValueError(
                    f"ZIP decompressed size exceeds limit ({max_size} bytes)"
                )

        # Extract all files (validated as safe)
        zip_ref.extractall(output_dir)

    def _extract_and_process_zip(self, zip_path: Path, output_dir: Path) -> int:
        """Extract ZIP file and handle nested ZIPs.

        Args:
            zip_path: Path to ZIP file to extract
            output_dir: Directory to extract files to

        Returns:
            Total number of files extracted (including from nested ZIPs)
        """
        total_files = 0

        # Extract main ZIP
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            filenames = zip_ref.namelist()
            self._extract_zip_safely(zip_ref, output_dir)
            total_files += len(filenames)

        # Delete the main ZIP file to avoid finding it when searching for nested ZIPs
        zip_path.unlink()

        # Check for nested ZIPs and extract them
        nested_zips = list(output_dir.glob("*.zip"))
        for nested_zip in nested_zips:
            logger.debug(f"Found nested ZIP: {nested_zip.name}")
            try:
                with zipfile.ZipFile(nested_zip, "r") as nested_ref:
                    self._extract_zip_safely(nested_ref, output_dir)
                    nested_count = len(nested_ref.namelist())
                    total_files += nested_count
                    logger.debug(f"Extracted {nested_count} files from nested ZIP")
                # Remove nested ZIP after extraction
                nested_zip.unlink()
            except zipfile.BadZipFile:
                logger.warning(
                    f"Nested file {nested_zip.name} is not a valid ZIP, keeping as-is"
                )
            except Exception as e:
                logger.warning(f"Failed to extract nested ZIP {nested_zip.name}: {e}")

        return total_files

    def _rename_extracted_documents(self, output_dir: Path) -> None:
        """Rename extracted documents based on their type.

        Renames files to standardized names:
        - Spec sheets → spec_sheet.pdf
        - Manuals → instruction_manual.pdf

        Args:
            output_dir: Directory containing extracted files
        """
        for file_path in output_dir.glob("*.pdf"):
            filename_lower = file_path.name.lower()

            # Determine new name based on file content indicators
            new_name = None
            if "spec" in filename_lower or "technical" in filename_lower:
                new_name = "spec_sheet.pdf"
            elif (
                "man" in filename_lower
                or "manual" in filename_lower
                or "instruction" in filename_lower
            ):
                new_name = "instruction_manual.pdf"

            # Rename if we identified the document type
            if new_name:
                new_path = output_dir / new_name
                # If target already exists, remove it first
                if new_path.exists():
                    new_path.unlink()
                file_path.rename(new_path)
                logger.debug(f"Renamed {file_path.name} → {new_name}")

    def _find_image_files(self, directory: Path) -> list[Path]:
        """Find all image files recursively in a directory (case-insensitive).

        Args:
            directory: Directory to search

        Returns:
            List of unique image file paths (deduplicated)
        """
        # Use both lowercase and uppercase patterns for case-insensitive matching
        image_extensions = [
            "*.jpg", "*.JPG",
            "*.jpeg", "*.JPEG",
            "*.png", "*.PNG",
            "*.webp", "*.WEBP"
        ]
        image_files = []
        for ext in image_extensions:
            image_files.extend(directory.rglob(ext))

        # Deduplicate using resolved paths (Windows filesystem is case-insensitive)
        # This prevents the same file from being found by both *.jpg and *.JPG patterns
        seen_paths = set()
        unique_files = []
        for img in image_files:
            resolved = img.resolve()
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                unique_files.append(img)

        return unique_files

    def _filter_unclassified_images(
        self, image_files: list[Path], product_dir: Path, project_dir: Path
    ) -> list[Path]:
        """Filter out images that are already in classified directories.

        Args:
            image_files: List of all image files
            product_dir: Product images directory
            project_dir: Project images directory

        Returns:
            List of images that need classification
        """
        return [
            img
            for img in image_files
            if not (img.parent == product_dir or img.parent == project_dir)
        ]

    def _is_duplicate_image(
        self, image_path: Path, product_dir: Path, project_dir: Path
    ) -> bool:
        """Check if an image file already exists in destination directories.

        Args:
            image_path: Path to image file
            product_dir: Product images directory
            project_dir: Project images directory

        Returns:
            True if image with same name exists in either directory
        """
        return (product_dir / image_path.name).exists() or (
            project_dir / image_path.name
        ).exists()

    def _move_classified_image(
        self,
        image_file: Path,
        classification: str,
        product_dir: Path,
        project_dir: Path,
    ) -> None:
        """Move image to appropriate directory based on classification.

        Args:
            image_file: Path to image file
            classification: Classification result ("product" or "project")
            product_dir: Product images directory
            project_dir: Project images directory

        Raises:
            FileNotFoundError: If image file doesn't exist
            OSError: If move operation fails
        """
        if classification == "product":
            dest = product_dir / image_file.name
            image_file.rename(dest)
            logger.info(f"✓ Product image: {image_file.name}")
        elif classification == "project":
            dest = project_dir / image_file.name
            image_file.rename(dest)
            logger.info(f"✓ Project image: {image_file.name}")
        else:
            # Fallback to product for unknown classifications
            dest = product_dir / image_file.name
            image_file.rename(dest)
            logger.warning(
                f"Unknown classification '{classification}', "
                f"defaulting to product: {image_file.name}"
            )

    def _cleanup_leftover_files(
        self, output_dir: Path, product_dir: Path, project_dir: Path
    ) -> None:
        """Clean up leftover ZIP files and empty directories.

        Args:
            output_dir: Root output directory
            product_dir: Product images directory (preserved)
            project_dir: Project images directory (preserved)
        """
        # Remove leftover ZIP files
        for zip_file in output_dir.rglob("*.zip"):
            try:
                zip_file.unlink()
                logger.debug(f"Removed leftover ZIP: {zip_file.name}")
            except (OSError, PermissionError) as e:
                logger.debug(f"Could not remove ZIP {zip_file.name}: {e}")

        # Remove empty directories (preserve images/ subdirs)
        images_dir = output_dir / "images"
        preserved_dirs = {product_dir, project_dir, images_dir}

        for subdir in sorted(output_dir.rglob("*"), reverse=True):
            if not subdir.is_dir() or subdir in preserved_dirs:
                continue

            try:
                if not any(subdir.iterdir()):  # Directory is empty
                    subdir.rmdir()
                    logger.debug(f"Removed empty directory: {subdir.name}")
            except (OSError, PermissionError) as e:
                logger.debug(f"Could not remove directory {subdir.name}: {e}")

    def _classify_and_organize_images(self, output_dir: Path) -> None:
        """Classify downloaded images as product or project using AI and organize into subdirectories.

        Args:
            output_dir: Directory containing extracted files
        """
        import time

        # Import here to avoid circular dependency
        from src.ai.image_classifier import classify_image_file

        # Find all image files
        image_files = self._find_image_files(output_dir)
        if not image_files:
            logger.debug("No images found in downloaded files")
            return

        # Create output directories
        product_dir = output_dir / "images" / "product"
        project_dir = output_dir / "images" / "project"
        product_dir.mkdir(parents=True, exist_ok=True)
        project_dir.mkdir(parents=True, exist_ok=True)

        # Filter out already-classified images
        images_to_classify = self._filter_unclassified_images(
            image_files, product_dir, project_dir
        )

        if len(images_to_classify) < len(image_files):
            skipped = len(image_files) - len(images_to_classify)
            logger.debug(f"Skipping {skipped} already-classified images")

        if not images_to_classify:
            logger.debug("All images already classified")
            return

        logger.info(f"Classifying {len(images_to_classify)} images using AI...")

        # Classify and move each image
        for image_file in images_to_classify:
            try:
                # Skip duplicates
                if self._is_duplicate_image(image_file, product_dir, project_dir):
                    logger.debug(f"Skipping duplicate: {image_file.name}")
                    image_file.unlink()
                    continue

                # Classify and move
                classification = classify_image_file(str(image_file))
                time.sleep(0.5)  # Rate limiting prevention
                self._move_classified_image(
                    image_file, classification, product_dir, project_dir
                )

            except (FileNotFoundError, OSError) as e:
                logger.warning(f"Failed to process image {image_file.name}: {e}")
                # Fallback: try to move to product dir
                try:
                    dest = product_dir / image_file.name
                    if not dest.exists() and image_file.exists():
                        image_file.rename(dest)
                    elif image_file.exists():
                        image_file.unlink()
                except (OSError, PermissionError):
                    logger.debug(f"Could not recover from error for {image_file.name}")

            except Exception as e:
                logger.error(f"Unexpected error classifying {image_file.name}: {e}")
                # Try to clean up the file
                try:
                    if image_file.exists():
                        image_file.unlink()
                except (OSError, PermissionError):
                    pass

        # Clean up leftover files
        self._cleanup_leftover_files(output_dir, product_dir, project_dir)
        logger.info("Organized images into product and project directories")

    def _login_and_inject_cookies(self) -> bool:
        """Login via API and inject cookies into Playwright browser.

        Returns:
            True if login successful, False otherwise
        """
        email = os.getenv("VIBIA_EMAIL")
        password = os.getenv("VIBIA_PASSWORD")

        if not email or not password:
            logger.warning("Vibia credentials not found in environment")
            return False

        try:
            logger.info(f"Logging in to Vibia as {email} via API...")

            # Login via API to get cookies
            vibia_auth = VibiaAuth(email=email, password=password)
            if not vibia_auth.login():
                logger.error("Failed to authenticate with Vibia API")
                return False

            # Extract cookies from httpx client and prepare for Playwright
            if not vibia_auth.client:
                logger.error("VibiaAuth client not initialized after login")
                return False

            cookies = []
            for cookie in vibia_auth.client.cookies.jar:
                # Skip cookies without name or value
                if not cookie.name or not cookie.value:
                    continue

                # Set domain to work across Vibia subdomains (www, app, api)
                # Default to .vibia.com if domain is None or doesn't contain vibia.com
                domain = cookie.domain or ""
                if not domain or "vibia.com" in domain:
                    domain = ".vibia.com"

                cookies.append(
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "domain": domain,
                        "path": cookie.path or "/",
                    }
                )

            if not cookies:
                logger.warning("No cookies obtained from API login")
                return False

            # Inject cookies into Playwright browser
            self._ensure_browser()
            assert self._page is not None

            # Get browser context from page
            context = self._page.context
            context.add_cookies(cookies)

            logger.success(
                f"Successfully logged in and injected {len(cookies)} cookies"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to login and inject cookies: {e}")
            return False

    def download_product_files(self, output_dir: Path) -> bool:
        """Download product files using Playwright browser automation.

        Downloads technical information and instruction manual by default.

        Args:
            output_dir: Directory to save downloaded files

        Returns:
            True if download successful, False otherwise
        """
        self._ensure_browser()
        assert self._page is not None

        # Save current product page URL before login
        product_url = self._page.url

        # Login via API and inject cookies into browser
        if not self._login_and_inject_cookies():
            logger.warning("Skipping file downloads - login failed")
            return False

        # Navigate to product page with authenticated session
        logger.info(f"Navigating to product page: {product_url}")
        self._page.goto(product_url, wait_until="networkidle")
        self._page.wait_for_timeout(2000)  # Give page time to load

        # Dismiss cookie banner if present
        cookie_selectors = [
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
            "#CybotCookiebotDialogBodyButtonAccept",
            'button:has-text("Accept all")',
            'button:has-text("Allow all")',
        ]
        for selector in cookie_selectors:
            try:
                self._page.click(selector, timeout=2000)
                logger.debug("Dismissed cookie banner")
                self._page.wait_for_timeout(500)
                break
            except Exception:
                continue

        try:
            logger.info("Looking for download trigger button...")

            # First, click the Download button to open the modal
            # Based on screenshot: button[data-qa="download-popup-open-inspirational"]
            download_trigger = self._page.locator(
                'button[data-qa="download-popup-open-inspirational"], button.vib-link:has-text("Download")'
            )

            if download_trigger.count() == 0:
                logger.error("Download trigger button not found on page")
                return False

            logger.info("Clicking Download button to open modal...")
            download_trigger.first.scroll_into_view_if_needed()
            download_trigger.first.click()

            # Wait for modal to appear and checkboxes to be ready
            logger.info("Download modal should now be open")

            # Wait specifically for one of the checkboxes to appear (indicates modal is fully loaded)
            try:
                self._page.wait_for_selector(
                    'input[name="specSheet"], input[name="manual"], input[name="images"]',
                    timeout=5000,
                )
                logger.debug("Checkboxes detected in modal")
            except Exception:
                logger.warning("Checkboxes not found after 5s wait, proceeding anyway")

            # Select checkboxes for documents and images
            # Based on screenshot: name="specSheet", name="manual", name="images"
            checkboxes_to_select = [
                ('input[name="specSheet"]', "Technical information"),
                ('input[name="manual"]', "Instruction manual"),
                ('input[name="images"]', "Images (HD)"),
            ]

            checked_count = 0
            for selector, label in checkboxes_to_select:
                checkbox = self._page.locator(selector)
                if checkbox.count() > 0:
                    checkbox.first.check(force=True)  # Force click even if obscured
                    checked_count += 1
                    logger.info(f"✓ {label} selected")
                else:
                    logger.debug(f"Checkbox not found: {label}")

            if checked_count == 0:
                logger.warning("No checkboxes found - trying to download anyway")

            # Wait for download package to be prepared (especially for large image packages)
            logger.info("Waiting for download package to be prepared (5s)...")
            self._page.wait_for_timeout(5000)

            # Setup download handler and click Download button inside modal
            output_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Clicking Download button in modal...")

            # Wait for download button to be visible and enabled
            download_button = self._page.locator(
                '#downloadArticle, button[data-qa="downloadArticle"]'
            )
            download_button.wait_for(state="visible", timeout=10000)

            # Check if button is disabled and wait for it to become enabled
            try:
                self._page.wait_for_function(
                    """() => {
                        const btn = document.querySelector('#downloadArticle, button[data-qa="downloadArticle"]');
                        return btn && !btn.disabled;
                    }""",
                    timeout=10000,
                )
                logger.debug("Download button is enabled")
            except Exception:
                logger.warning("Download button may still be disabled, trying anyway")

            # Increase timeout for image downloads (can be large)
            with self._page.expect_download(timeout=180000) as download_info:
                # Click the download button (don't force - let it fail if actually disabled)
                download_button.click()

            download = download_info.value

            # Save the downloaded file
            zip_path = output_dir / "vibia_documents.zip"
            download.save_as(zip_path)

            logger.success(f"Downloaded file to {zip_path}")

            # Extract ZIP contents securely (handle nested ZIPs)
            try:
                extracted_count = self._extract_and_process_zip(zip_path, output_dir)
                logger.success(f"Extracted {extracted_count} files to {output_dir}")

                # Rename files based on document type
                self._rename_extracted_documents(output_dir)

                # Classify and organize images
                self._classify_and_organize_images(output_dir)

            except zipfile.BadZipFile:
                logger.error("Downloaded file is not a valid ZIP")
                return False
            finally:
                # Remove ZIP file after extraction
                if zip_path.exists():
                    zip_path.unlink()

            return True

        except Exception as e:
            logger.error(f"Error downloading via browser: {e}")
            return False
