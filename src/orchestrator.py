"""Orchestrator for managing scraping workflow.

Following CLAUDE.md: pure functions with clear separation of concerns.
"""

from pathlib import Path
from typing import Optional

from loguru import logger

from src.types import SKU, ProductData, Manufacturer
from src.scrapers.lodes_scraper import LodesScraper
from src.exporters.woocommerce_csv import export_to_woocommerce_csv
from src.exporters.excel_exporter import export_to_excel
from src.ai.description_generator import generate_description
from src.ai.german_translator import translate_product_data
from src.downloaders.asset_downloader import download_pdf


class ScraperOrchestrator:
    """Coordinates scraping, data collection, and export workflow."""

    def __init__(self):
        """Initialize orchestrator with available scrapers."""
        self.scrapers = {
            "lodes": LodesScraper,
            # Future scrapers will be added here
            # "vibia": VibiaScraper,
        }

    def scrape_products(
        self,
        manufacturer: str,
        skus: list[str] | None = None,
        category_url: str | None = None,
        download_images: bool = True,
        ai_descriptions: bool = False,
        translate_to_german: bool = False,
        output_dir: str = "output",
    ) -> list[ProductData]:
        """Scrape products from manufacturer website.

        Args:
            manufacturer: Manufacturer name (e.g., 'lodes')
            skus: List of product SKUs/slugs to scrape (optional if category_url provided)
            category_url: Category URL to discover products from (optional if skus provided)
            download_images: Whether to download product images
            ai_descriptions: Whether to generate unique descriptions with AI
            translate_to_german: Whether to translate content to German if not already in German
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

        if manufacturer_lower not in self.scrapers:
            available = ", ".join(self.scrapers.keys())
            raise ValueError(
                f"Manufacturer '{manufacturer}' not supported. "
                f"Available: {available}"
            )

        scraper_class = self.scrapers[manufacturer_lower]
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
                    product = scraper.scrape_product(sku)

                    if ai_descriptions:
                        try:
                            new_description = generate_description(product)
                            product.description = new_description
                            logger.info(
                                f"✓ Generated AI description for {product.name}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to generate AI description for {sku}: {e}"
                            )

                    # Translate to German if requested and not already in German
                    if translate_to_german and product.scraped_language != "de":
                        try:
                            product = translate_product_data(product)
                            product.translated_to_german = True
                            logger.info(
                                f"✓ Translated {product.name} from {product.scraped_language} to German"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to translate {sku} to German: {e}")

                    products.append(product)

                    if download_images and product.images:
                        scraper.download_product_images(product, f"{output_dir}/images")

                    if product.attributes.get("Datasheet URL"):
                        try:
                            pdf_url = product.attributes["Datasheet URL"]
                            download_pdf(
                                pdf_url,
                                product.sku,
                                product.manufacturer,
                                f"{output_dir}/datasheets",
                            )
                            logger.info(f"✓ Downloaded datasheet for {product.sku}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to download datasheet for {product.sku}: {e}"
                            )

                    logger.info(f"✓ Scraped: {product.name} ({sku})")

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

    def run_full_pipeline(
        self,
        manufacturer: str,
        skus: list[str] | None = None,
        category_url: str | None = None,
        download_images: bool = True,
        ai_descriptions: bool = False,
        translate_to_german: bool = False,
        output_dir: str = "output",
    ) -> tuple[list[ProductData], Path, Path]:
        """Run complete scraping and export pipeline.

        Args:
            manufacturer: Manufacturer name
            skus: List of product SKUs/slugs (optional if category_url provided)
            category_url: Category URL to discover products from (optional if skus provided)
            download_images: Whether to download images
            ai_descriptions: Whether to generate unique descriptions with AI
            translate_to_german: Whether to translate content to German
            output_dir: Output directory

        Returns:
            Tuple of (products, csv_path, excel_path)
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

        # Step 1: Scrape products
        products = self.scrape_products(
            manufacturer,
            skus,
            category_url,
            download_images,
            ai_descriptions,
            translate_to_german,
            output_dir,
        )

        if not products:
            logger.warning("No products were successfully scraped")
            raise ValueError("Scraping failed for all products")

        # Step 2: Export to CSV and Excel
        csv_path, excel_path = self.export_products(products, output_dir)

        logger.info("=" * 60)
        logger.info(f"Pipeline complete!")
        logger.info(f"Products scraped: {len(products)}")
        logger.info(f"CSV: {csv_path}")
        logger.info(f"Excel: {excel_path}")
        logger.info("=" * 60)

        return products, csv_path, excel_path


def scrape_and_export(
    manufacturer: str,
    skus: list[str] | None = None,
    category_url: str | None = None,
    download_images: bool = True,
    ai_descriptions: bool = False,
    translate_to_german: bool = False,
    output_dir: str = "output",
) -> tuple[list[ProductData], Path, Path]:
    """Convenience function for running full scraping pipeline.

    Args:
        manufacturer: Manufacturer name (e.g., 'lodes')
        skus: List of product SKUs/slugs to scrape (optional if category_url provided)
        category_url: Category URL to discover products from (optional if skus provided)
        download_images: Whether to download product images
        ai_descriptions: Whether to generate unique descriptions with AI
        translate_to_german: Whether to translate content to German
        output_dir: Output directory

    Returns:
        Tuple of (products, csv_path, excel_path)
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
