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
        skus: list[str],
        download_images: bool = True,
        output_dir: str = "output",
    ) -> list[ProductData]:
        """Scrape products from manufacturer website.

        Args:
            manufacturer: Manufacturer name (e.g., 'lodes')
            skus: List of product SKUs/slugs to scrape
            download_images: Whether to download product images
            output_dir: Base output directory

        Returns:
            List of scraped product data

        Raises:
            ValueError: If manufacturer is not supported
            Exception: If scraping fails
        """
        manufacturer_lower = manufacturer.lower()

        if manufacturer_lower not in self.scrapers:
            available = ", ".join(self.scrapers.keys())
            raise ValueError(
                f"Manufacturer '{manufacturer}' not supported. "
                f"Available: {available}"
            )

        scraper_class = self.scrapers[manufacturer_lower]
        products = []

        logger.info(f"Starting scrape for {len(skus)} products from {manufacturer}")

        with scraper_class() as scraper:
            for sku_str in skus:
                sku = SKU(sku_str)
                try:
                    product = scraper.scrape_product(sku)
                    products.append(product)

                    if download_images and product.images:
                        scraper.download_product_images(product, f"{output_dir}/images")

                    logger.info(f"✓ Scraped: {product.name} ({sku})")

                except Exception as e:
                    logger.error(f"✗ Failed to scrape {sku}: {e}")
                    # Continue with next product instead of failing entire batch

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
        skus: list[str],
        download_images: bool = True,
        output_dir: str = "output",
    ) -> tuple[list[ProductData], Path, Path]:
        """Run complete scraping and export pipeline.

        Args:
            manufacturer: Manufacturer name
            skus: List of product SKUs/slugs
            download_images: Whether to download images
            output_dir: Output directory

        Returns:
            Tuple of (products, csv_path, excel_path)
        """
        logger.info("=" * 60)
        logger.info(f"Starting full pipeline for {manufacturer}")
        logger.info(f"SKUs: {skus}")
        logger.info("=" * 60)

        # Step 1: Scrape products
        products = self.scrape_products(manufacturer, skus, download_images, output_dir)

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
    skus: list[str],
    download_images: bool = True,
    output_dir: str = "output",
) -> tuple[list[ProductData], Path, Path]:
    """Convenience function for running full scraping pipeline.

    Args:
        manufacturer: Manufacturer name (e.g., 'lodes')
        skus: List of product SKUs/slugs to scrape
        download_images: Whether to download product images
        output_dir: Output directory

    Returns:
        Tuple of (products, csv_path, excel_path)
    """
    orchestrator = ScraperOrchestrator()
    return orchestrator.run_full_pipeline(
        manufacturer, skus, download_images, output_dir
    )
