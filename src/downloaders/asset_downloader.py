"""Asset downloader for images and PDFs.

Following CLAUDE.md: pure, testable functions with clear responsibilities.
"""

import os
from pathlib import Path
import requests
from loguru import logger

from src.models import ImageUrl, SKU, Manufacturer
from src.utils.retry_handler import retry_with_backoff
from src.ai.image_classifier import classify_image_url, ImageType


def _generate_image_filename(image_type: ImageType | None, index: int, ext: str) -> str:
    """Generate filename based on image type and index (pure function).

    Args:
        image_type: Classification type ("product" or "project")
        index: Image index (0 = first image)
        ext: File extension including dot (e.g., ".jpg")

    Returns:
        Generated filename

    Examples:
        >>> _generate_image_filename("product", 0, ".jpg")
        "featured.jpg"
        >>> _generate_image_filename("product", 1, ".jpg")
        "product_01.jpg"
        >>> _generate_image_filename("project", 2, ".jpg")
        "project_02.jpg"
        >>> _generate_image_filename(None, 0, ".jpg")
        "featured.jpg"
    """
    if image_type == "product" and index == 0:
        # First product image is the featured image
        return f"featured{ext}"
    elif image_type == "product":
        return f"product_{index:02d}{ext}"
    elif image_type == "project":
        return f"project_{index:02d}{ext}"
    else:
        # Fallback to old naming for backwards compatibility
        return f"{index:02d}{ext}" if index > 0 else f"featured{ext}"


def download_image(
    image_url: ImageUrl,
    sku: SKU,
    manufacturer: Manufacturer,
    output_dir: str = "output/images",
    index: int = 0,
    flat_structure: bool = False,
    image_type: ImageType | None = None,
    classify_images: bool = True,
) -> Path:
    """Download image and save to organized folder structure.

    Args:
        image_url: URL of the image to download
        sku: Product SKU for folder organization
        manufacturer: Manufacturer name for folder organization
        output_dir: Base output directory
        index: Image index for naming (0 = featured image)
        flat_structure: If True, save directly to output_dir without manufacturer/sku subdirs
        image_type: Pre-classified image type ("product" or "project"). If None and classify_images=True, will classify automatically
        classify_images: If True, classify image type using AI (default: True)

    Returns:
        Path to downloaded image file

    Raises:
        requests.RequestException: If download fails after retries
    """
    # Classify image if needed
    if image_type is None and classify_images:
        try:
            image_type = classify_image_url(image_url)
        except Exception as e:
            logger.warning(f"Failed to classify image, defaulting to 'project': {e}")
            image_type = "project"

    # Create directory structure
    if flat_structure:
        # Direct to output_dir (e.g., output/{sku}/images/)
        image_dir = Path(output_dir)
    else:
        # Legacy structure: output/images/{manufacturer}/{sku}/
        image_dir = Path(output_dir) / manufacturer / sku
    image_dir.mkdir(parents=True, exist_ok=True)

    # Determine file extension from URL
    ext = _get_file_extension(image_url)

    # Generate filename based on image type
    filename = _generate_image_filename(image_type, index, ext)
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
    flat_structure: bool = False,
) -> Path:
    """Download PDF datasheet and save to organized folder structure.

    Args:
        pdf_url: URL of the PDF to download
        sku: Product SKU for naming
        manufacturer: Manufacturer name for folder organization
        output_dir: Base output directory
        flat_structure: If True, save directly to output_dir without manufacturer subdir

    Returns:
        Path to downloaded PDF file

    Raises:
        requests.RequestException: If download fails after retries
    """
    # Create directory structure
    if flat_structure:
        # Direct to output_dir (e.g., output/{sku}/datasheets/)
        pdf_dir = Path(output_dir)
    else:
        # Legacy structure: output/pdfs/{manufacturer}/
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
