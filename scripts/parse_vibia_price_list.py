"""CLI script to parse Vibia price list PDF and generate JSON output."""

import argparse
import sys

from loguru import logger

from scripts.cli_utils import setup_logging
from scripts.parsers.vibia_pdf_parser import VibiaTableParser
from scripts.parsers.pdf_parser_base import write_json_atomic


def main():
    """Main entry point for Vibia price list parser."""
    parser = argparse.ArgumentParser(
        description="Parse Vibia price list PDF and generate JSON output"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        required=True,
        help="Path to Vibia price list PDF file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/vibia_price_list_data.json",
        help="Output JSON file path (default: output/vibia_price_list_data.json)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=None,
        help="Start page number (1-indexed, default: all pages)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        default=None,
        help="End page number (1-indexed, default: all pages)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse PDF but don't write output file",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging to console",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging("vibia_parser_{time}.log", args.verbose)

    logger.info("=" * 60)
    logger.info("Vibia Price List Parser")
    logger.info("=" * 60)
    logger.info(f"PDF: {args.pdf}")
    if args.start_page and args.end_page:
        logger.info(f"Pages: {args.start_page}-{args.end_page}")
    else:
        logger.info("Pages: ALL")
    logger.info(f"Output: {args.output}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 60)

    try:
        # Parse PDF
        vibia_parser = VibiaTableParser(args.pdf, args.start_page, args.end_page)
        result = vibia_parser.parse_price_list()

        # Write output
        if args.dry_run:
            logger.info("Dry run mode - skipping file write")
            logger.info(
                f"Would write {len(result['products'])} products to {args.output}"
            )
        else:
            write_json_atomic(result, args.output)
            logger.info(
                f"Successfully wrote {len(result['products'])} products to {args.output}"
            )

        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Parsing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
