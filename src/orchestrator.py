"""Orchestrator for managing scraping workflow.

Following CLAUDE.md: pure functions with clear separation of concerns.
"""

from pathlib import Path

from loguru import logger

from src.models import SKU, ProductData
from src.scrapers.registry import get_scraper_class
from src.exporters.woocommerce_csv import export_to_woocommerce_csv
from src.exporters.excel_exporter import export_to_excel
from src.ai.description_generator import (
    generate_description,
    generate_short_description,
)
from src.ai.german_translator import translate_product_data
from src.downloaders.asset_downloader import download_pdf


class ScraperOrchestrator:
    """Coordinates scraping, data collection, and export workflow."""

    def scrape_products(
        self,
        manufacturer: str,
        skus: list[str] | None = None,
        category_url: str | None = None,
        download_images: bool = True,
        ai_descriptions: bool = False,
        translate_to_german: bool = True,
        output_dir: str = "output",
    ) -> list[ProductData]:
        """Scrape products from manufacturer website.

        Args:
            manufacturer: Manufacturer name (e.g., 'lodes')
            skus: List of product SKUs/slugs to scrape (optional if category_url provided)
            category_url: Category URL to discover products from (optional if skus provided)
            download_images: Whether to download product images
            ai_descriptions: Whether to generate unique descriptions with AI
            translate_to_german: Whether to translate content to German (default: True)
            output_dir: Base output directory

        Returns:
            List of scraped product data

        Raises:
            ValueError: If manufacturer is not supported or neither skus nor category_url provided
            Exception: If scraping fails
        """
        if not skus and not category_url:
            raise ValueError("Either skus or category_url must be provided")

        manufacturer_lower = manufacturer.lower()

        # Get scraper class from registry
        scraper_class = get_scraper_class(manufacturer_lower)
        products = []

        with scraper_class() as scraper:
            if category_url:
                logger.info(f"Discovering products from category: {category_url}")
                try:
                    skus = [str(sku) for sku in scraper.scrape_category(category_url)]
                    logger.info(f"Found {len(skus)} products in category")
                except Exception as e:
                    logger.error(f"Failed to scrape category {category_url}: {e}")
                    raise

            logger.info(f"Starting scrape for {len(skus)} products from {manufacturer}")

            for sku_str in skus:
                sku = SKU(sku_str)
                try:
                    scraped_products = scraper.scrape_product(sku, output_base=output_dir)

                    for product in scraped_products:
                        if ai_descriptions:
                            try:
                                new_description = generate_description(product)
                                product.description = new_description
                                logger.info(
                                    f"✓ Generated AI description for {product.name}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to generate AI description for {product.sku}: {e}"
                                )

                        # Translate to German if requested
                        # Note: Always translate when enabled, as some manufacturers have
                        # Italian content on their German pages (e.g., Lodes /de/ has Italian text)
                        if translate_to_german:
                            try:
                                product = translate_product_data(product)
                                product.translated_to_german = True
                                logger.info(f"✓ Translated {product.name} to German")
                            except Exception as e:
                                logger.warning(
                                    f"Failed to translate {product.sku} to German: {e}"
                                )

                        # Generate short description only when AI descriptions enabled
                        if ai_descriptions:
                            try:
                                short_desc = generate_short_description(
                                    product, max_words=20
                                )
                                product.short_description = short_desc
                                logger.info(
                                    f"✓ Generated short description for {product.name}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to generate short description for {product.sku}: {e}"
                                )

                        # Note: Image and PDF downloading now handled per-product
                        # in run_full_pipeline for better organization
                        products.append(product)
                        logger.info(f"✓ Scraped: {product.name} ({product.sku})")

                except Exception as e:
                    logger.error(f"✗ Failed to scrape {sku}: {e}")

        logger.info(
            f"Scraping complete: {len(products)}/{len(skus)} products successful"
        )
        return products

    def export_products(
        self,
        products: list[ProductData],
        output_dir: str = "output",
        csv_filename: str = "products.csv",
        excel_filename: str = "products.xlsx",
    ) -> tuple[Path, Path]:
        """Export products to CSV and XLSX formats.

        Args:
            products: List of product data to export
            output_dir: Output directory path
            csv_filename: CSV filename
            excel_filename: Excel filename

        Returns:
            Tuple of (csv_path, excel_path)

        Raises:
            ValueError: If products list is empty
        """
        if not products:
            raise ValueError("Cannot export empty product list")

        csv_path = export_to_woocommerce_csv(products, f"{output_dir}/{csv_filename}")
        excel_path = export_to_excel(products, f"{output_dir}/{excel_filename}")

        logger.info(f"Export complete: {csv_path} and {excel_path}")
        return csv_path, excel_path

    def _group_products_by_base_sku(
        self, products: list[ProductData]
    ) -> dict[str, list[ProductData]]:
        """Group products by their base SKU (parent for variations, own SKU for parents).

        Args:
            products: List of all scraped products

        Returns:
            Dictionary mapping base SKU to list of products (parent + variations)
        """
        grouped = {}

        for i, product in enumerate(products):
            # For variations: use their parent_sku (check is not None to handle empty strings)
            if product.parent_sku is not None:
                base_sku = product.parent_sku
            # For variable parents: use their own SKU (even if empty)
            elif product.product_type == "variable":
                base_sku = product.sku
            # For simple products: use their own SKU
            else:
                base_sku = product.sku

            # If base_sku is empty, use product family name to distinguish different products
            # This prevents multiple product families from being grouped together
            if not base_sku:
                # Extract family name from product name (e.g., "Kelly, Design by..." -> "Kelly")
                family_name = (
                    product.name.split(",")[0].strip()
                    if product.name
                    else f"product-{i}"
                )
                base_sku = f"_empty_{family_name}"

            # Group products by base_sku
            if base_sku not in grouped:
                grouped[base_sku] = []
            grouped[base_sku].append(product)

        return grouped

    def run_full_pipeline(
        self,
        manufacturer: str,
        skus: list[str] | None = None,
        category_url: str | None = None,
        download_images: bool = True,
        ai_descriptions: bool = False,
        translate_to_german: bool = True,
        output_dir: str = "output",
    ) -> tuple[list[ProductData], list[Path], list[Path]]:
        """Run complete scraping and export pipeline with per-product organization.

        Args:
            manufacturer: Manufacturer name
            skus: List of product SKUs/slugs (optional if category_url provided)
            category_url: Category URL to discover products from (optional if skus provided)
            download_images: Whether to download images
            ai_descriptions: Whether to generate unique descriptions with AI
            translate_to_german: Whether to translate content to German (default: True)
            output_dir: Base output directory

        Returns:
            Tuple of (all_products, list_of_csv_paths, list_of_excel_paths)

        Note:
            Creates separate folders per product: {output_dir}/{sku}/
            Each folder contains: products.csv, products.xlsx, images/, datasheets/
        """
        logger.info("=" * 60)
        logger.info(f"Starting full pipeline for {manufacturer}")
        if skus:
            logger.info(f"SKUs: {skus}")
        if category_url:
            logger.info(f"Category: {category_url}")
        if ai_descriptions:
            logger.info("AI descriptions: ENABLED")
        logger.info("=" * 60)

        # Step 1: Scrape products (without downloading assets yet)
        products = self.scrape_products(
            manufacturer,
            skus,
            category_url,
            download_images=False,  # Assets will be downloaded per-product below
            ai_descriptions=ai_descriptions,
            translate_to_german=translate_to_german,
            output_dir=output_dir,
        )

        if not products:
            logger.warning("No products were successfully scraped")
            raise ValueError("Scraping failed for all products")

        # Step 2: Group products by base SKU (parent + variations together)
        grouped_products = self._group_products_by_base_sku(products)
        logger.info(
            f"Grouped {len(products)} products into {len(grouped_products)} product families"
        )

        # Step 3: Process each product group separately
        csv_paths = []
        excel_paths = []

        for base_sku, product_group in grouped_products.items():
            logger.info(
                f"Processing product group: {base_sku} ({len(product_group)} products)"
            )

            # Generate folder name (handle empty base_sku with _empty_ prefix)
            if base_sku.startswith("_empty_"):
                # Extract family name from the _empty_ prefix
                folder_name = base_sku[7:]  # Remove "_empty_" prefix
            elif not base_sku:
                # Shouldn't happen anymore, but keep as fallback
                # Find first variation with non-empty SKU for folder name
                folder_name = None
                for product in product_group:
                    if product.product_type == "variation" and product.sku:
                        # Use first part of SKU before dash, or first 20 chars
                        if "-" in product.sku:
                            folder_name = product.sku.split("-")[0]
                        else:
                            folder_name = product.sku[:20]
                        break
                # Fallback: use product name or generic name
                if not folder_name:
                    if product_group[0].name:
                        # Use first word of product name
                        folder_name = product_group[0].name.split()[0]
                    else:
                        folder_name = "product"
            else:
                folder_name = str(base_sku)

            # Create product-specific output folder
            product_output_dir = Path(output_dir) / folder_name
            product_output_dir.mkdir(parents=True, exist_ok=True)

            # Step 3a: Download images and PDFs if requested
            if download_images:
                vibia_download_success = False

                # Vibia-specific: Download documents and images from modal
                if manufacturer.lower() == "vibia":
                    logger.info(
                        f"Attempting Vibia-specific document download for {folder_name}"
                    )
                    try:
                        scraper_class = get_scraper_class(manufacturer)
                        with scraper_class() as scraper:
                            # Use first product's SKU to build the product URL
                            first_product = product_group[0]
                            vibia_download_success = scraper.download_product_files(
                                sku=first_product.sku,
                                output_dir=product_output_dir,
                            )
                            if vibia_download_success:
                                logger.info(
                                    f"Successfully downloaded Vibia documents for {folder_name}"
                                )
                            else:
                                logger.warning(
                                    f"Vibia document download failed for {folder_name}, falling back to URL-based downloads"
                                )
                    except Exception as e:
                        logger.warning(
                            f"Vibia document download error for {folder_name}: {e}, falling back to URL-based downloads"
                        )

                # Download images for all products in group (skip if Vibia UI download succeeded)
                if not vibia_download_success:
                    for product in product_group:
                        if product.images:
                            images_dir = str(product_output_dir / "images")
                            for idx, image_url in enumerate(product.images):
                                try:
                                    from src.downloaders.asset_downloader import (
                                        download_image,
                                    )

                                    download_image(
                                        image_url,
                                        product.sku
                                        or folder_name,  # Use folder_name if product.sku is empty
                                        manufacturer,
                                        output_dir=images_dir,
                                        index=idx,
                                        flat_structure=True,
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to download image {image_url}: {e}"
                                    )

                # Download PDF for the product family (use first product with datasheet_url)
                for product in product_group:
                    logger.debug(
                        f"Checking product {product.sku} for datasheet_url: {getattr(product, 'datasheet_url', 'NOT_FOUND')}"
                    )
                    if hasattr(product, "datasheet_url") and product.datasheet_url:
                        datasheets_dir = str(product_output_dir / "datasheets")
                        logger.info(
                            f"Downloading datasheet for {folder_name} from {product.datasheet_url}"
                        )
                        try:
                            download_pdf(
                                product.datasheet_url,
                                folder_name,  # Use folder_name for PDF naming
                                manufacturer,
                                output_dir=datasheets_dir,
                                flat_structure=True,
                            )
                            break  # Only download once per product family
                        except Exception as e:
                            logger.warning(
                                f"Failed to download datasheet for {folder_name}: {e}"
                            )

                # Download installation manual for the product family
                for product in product_group:
                    if (
                        hasattr(product, "installation_manual_url")
                        and product.installation_manual_url
                    ):
                        manuals_dir = str(product_output_dir / "installation_manuals")
                        logger.info(
                            f"Downloading installation manual for {folder_name} from {product.installation_manual_url}"
                        )
                        try:
                            download_pdf(
                                product.installation_manual_url,
                                f"{folder_name}_installation",  # Add suffix to differentiate
                                manufacturer,
                                output_dir=manuals_dir,
                                flat_structure=True,
                            )
                            break  # Only download once per product family
                        except Exception as e:
                            logger.warning(
                                f"Failed to download installation manual for {folder_name}: {e}"
                            )

            # Step 3b: Export CSV and Excel for this product group
            csv_path = export_to_woocommerce_csv(
                product_group, str(product_output_dir / "products.csv")
            )
            excel_path = export_to_excel(
                product_group, str(product_output_dir / "products.xlsx")
            )

            csv_paths.append(csv_path)
            excel_paths.append(excel_path)

            logger.info(f"✓ Exported {folder_name}: {csv_path}")

        logger.info("=" * 60)
        logger.info("Pipeline complete!")
        logger.info(f"Products scraped: {len(products)}")
        logger.info(f"Product families: {len(grouped_products)}")
        logger.info(f"CSV files: {len(csv_paths)}")
        logger.info(f"Excel files: {len(excel_paths)}")
        logger.info("=" * 60)

        return products, csv_paths, excel_paths


def scrape_and_export(
    manufacturer: str,
    skus: list[str] | None = None,
    category_url: str | None = None,
    download_images: bool = True,
    ai_descriptions: bool = False,
    translate_to_german: bool = True,
    output_dir: str = "output",
) -> tuple[list[ProductData], list[Path], list[Path]]:
    """Convenience function for running full scraping pipeline.

    Args:
        manufacturer: Manufacturer name (e.g., 'lodes')
        skus: List of product SKUs/slugs to scrape (optional if category_url provided)
        category_url: Category URL to discover products from (optional if skus provided)
        download_images: Whether to download product images
        ai_descriptions: Whether to generate unique descriptions with AI
        translate_to_german: Whether to translate content to German (default: True)
        output_dir: Output directory

    Returns:
        Tuple of (products, list_of_csv_paths, list_of_excel_paths)
    """
    orchestrator = ScraperOrchestrator()
    return orchestrator.run_full_pipeline(
        manufacturer,
        skus,
        category_url,
        download_images,
        ai_descriptions,
        translate_to_german,
        output_dir,
    )
