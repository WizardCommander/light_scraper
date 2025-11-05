"""Command-line interface for product scraper.

Usage:
    python -m src.cli --manufacturer lodes --skus kelly,megaphone,a-tube-suspension
    python -m src.cli --manufacturer lodes --skus-file skus.txt
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from src.orchestrator import scrape_and_export


def setup_logging(verbose: bool = False) -> None:
    """Configure loguru logging.

    Args:
        verbose: Whether to enable debug logging
    """
    logger.remove()  # Remove default handler

    log_level = "DEBUG" if verbose else "INFO"
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(sys.stderr, format=log_format, level=log_level, colorize=True)
    logger.add(
        "logs/scraper_{time:YYYY-MM-DD}.log",
        format=log_format,
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
    )


def read_skus_from_file(file_path: str) -> list[str]:
    """Read SKUs from text file (one per line).

    Args:
        file_path: Path to file containing SKUs

    Returns:
        List of SKU strings

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"SKU file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        skus = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    return skus


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Scrape product data from manufacturer websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape specific products from Lodes
  python -m src.cli --manufacturer lodes --skus kelly,megaphone,a-tube-suspension

  # Read SKUs from file
  python -m src.cli --manufacturer lodes --skus-file lodes_skus.txt

  # Scrape entire category
  python -m src.cli --manufacturer lodes --category https://www.lodes.com/en/collections/suspension/

  # Skip image downloads
  python -m src.cli --manufacturer lodes --skus kelly --no-images

  # Custom output directory
  python -m src.cli --manufacturer lodes --skus kelly --output my_output
        """,
    )

    parser.add_argument(
        "--manufacturer",
        "-m",
        required=True,
        choices=["lodes"],  # Will expand as more scrapers are added
        help="Manufacturer to scrape from",
    )

    sku_group = parser.add_mutually_exclusive_group(required=True)
    sku_group.add_argument(
        "--skus",
        "-s",
        help="Comma-separated list of product SKUs/slugs",
    )
    sku_group.add_argument(
        "--skus-file",
        "-f",
        help="Path to file containing SKUs (one per line)",
    )
    sku_group.add_argument(
        "--category",
        "-c",
        help="Category/collection URL to scrape all products from",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="output",
        help="Output directory (default: output)",
    )

    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip downloading product images",
    )

    parser.add_argument(
        "--ai-descriptions",
        action="store_true",
        help="Generate unique descriptions using AI (requires ANTHROPIC_API_KEY)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Get SKU list or category URL
    skus = None
    category_url = None

    if args.skus:
        skus = [sku.strip() for sku in args.skus.split(",")]
    elif args.skus_file:
        try:
            skus = read_skus_from_file(args.skus_file)
        except FileNotFoundError as e:
            logger.error(str(e))
            return 1
    elif args.category:
        category_url = args.category

    if not skus and not category_url:
        logger.error("No SKUs or category URL provided")
        return 1

    # Run scraper
    try:
        products, csv_path, excel_path = scrape_and_export(
            manufacturer=args.manufacturer,
            skus=skus,
            category_url=category_url,
            download_images=not args.no_images,
            ai_descriptions=args.ai_descriptions,
            output_dir=args.output,
        )

        logger.success(f"Successfully scraped {len(products)} products!")
        logger.info(f"CSV: {csv_path}")
        logger.info(f"Excel: {excel_path}")

        return 0

    except Exception as e:
        logger.exception(f"Scraping failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
