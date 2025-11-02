"""Asset downloader for images and PDFs.

Following CLAUDE.md: pure, testable functions with clear responsibilities.
"""

import os
from pathlib import Path
from typing import Callable
import requests
from loguru import logger

from src.types import ImageUrl, SKU, Manufacturer
from src.utils.retry_handler import retry_with_backoff


def download_image(
    image_url: ImageUrl,
    sku: SKU,
    manufacturer: Manufacturer,
    output_dir: str = "output/images",
    index: int = 0,
) -> Path:
    """Download image and save to organized folder structure.

    Args:
        image_url: URL of the image to download
        sku: Product SKU for folder organization
        manufacturer: Manufacturer name for folder organization
        output_dir: Base output directory
        index: Image index for naming (0 = featured image)

    Returns:
        Path to downloaded image file

    Raises:
        requests.RequestException: If download fails after retries
    """
    # Create directory structure: output/images/{manufacturer}/{sku}/
    image_dir = Path(output_dir) / manufacturer / sku
    image_dir.mkdir(parents=True, exist_ok=True)

    # Determine file extension from URL
    ext = _get_file_extension(image_url)
    filename = f"{index:02d}{ext}" if index > 0 else f"featured{ext}"
    file_path = image_dir / filename

    def _download() -> None:
        response = requests.get(image_url, timeout=30, stream=True)
        response.raise_for_status()

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    retry_with_backoff(_download, max_retries=3)
    logger.info(f"Downloaded image: {file_path}")

    return file_path


def download_pdf(
    pdf_url: str,
    sku: SKU,
    manufacturer: Manufacturer,
    output_dir: str = "output/pdfs",
) -> Path:
    """Download PDF datasheet and save to organized folder structure.

    Args:
        pdf_url: URL of the PDF to download
        sku: Product SKU for naming
        manufacturer: Manufacturer name for folder organization
        output_dir: Base output directory

    Returns:
        Path to downloaded PDF file

    Raises:
        requests.RequestException: If download fails after retries
    """
    # Create directory structure: output/pdfs/{manufacturer}/
    pdf_dir = Path(output_dir) / manufacturer
    pdf_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{sku}.pdf"
    file_path = pdf_dir / filename

    def _download() -> None:
        response = requests.get(pdf_url, timeout=30, stream=True)
        response.raise_for_status()

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    retry_with_backoff(_download, max_retries=3)
    logger.info(f"Downloaded PDF: {file_path}")

    return file_path


def _get_file_extension(url: str) -> str:
    """Extract file extension from URL.

    Args:
        url: URL to parse

    Returns:
        File extension including dot (e.g., '.jpg')
    """
    path = url.split("?")[0]  # Remove query parameters
    ext = os.path.splitext(path)[1].lower()

    # Default to .jpg if no extension found
    return ext if ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"] else ".jpg"
